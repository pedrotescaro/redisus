"""
REDISUS - Sistema de Diagnóstico de Feridas
Módulo de Tracking de Evolução

Este módulo compara fotos ao longo do tempo para calcular
evolução da ferida e eficácia do tratamento.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger

from ..core.config import TissueType, TISSUE_NAMES
from ..diagnosis.tissue_segmenter import TissueSegmentationResult, WoundAreaCalculator


@dataclass
class WoundMeasurement:
    """Medição de ferida em um ponto no tempo"""
    timestamp: datetime
    image_path: Optional[str]
    area_pixels: int
    area_cm2: Optional[float]
    tissue_percentages: Dict[str, float]
    segmentation_mask: Optional[np.ndarray] = None
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "image_path": self.image_path,
            "area_pixels": self.area_pixels,
            "area_cm2": self.area_cm2,
            "tissue_percentages": self.tissue_percentages,
            "notes": self.notes,
        }


@dataclass
class EvolutionReport:
    """Relatório de evolução entre duas medições"""
    current: WoundMeasurement
    previous: WoundMeasurement
    days_between: int
    
    # Mudanças de área
    area_change_pixels: int
    area_change_cm2: Optional[float]
    area_change_percent: float
    
    # Mudanças de tecido
    tissue_changes: Dict[str, float]  # Positivo = aumento, Negativo = redução
    
    # Classificação da evolução
    evolution_status: str  # "improving", "stable", "worsening"
    healing_rate_percent_per_week: float
    estimated_healing_weeks: Optional[int]
    
    def to_dict(self) -> Dict:
        return {
            "current_date": self.current.timestamp.isoformat(),
            "previous_date": self.previous.timestamp.isoformat(),
            "days_between": self.days_between,
            "area_change": {
                "pixels": self.area_change_pixels,
                "cm2": self.area_change_cm2,
                "percent": round(self.area_change_percent, 2),
            },
            "tissue_changes": {k: round(v, 2) for k, v in self.tissue_changes.items()},
            "evolution_status": self.evolution_status,
            "healing_rate_percent_per_week": round(self.healing_rate_percent_per_week, 2),
            "estimated_healing_weeks": self.estimated_healing_weeks,
        }
    
    def get_summary(self) -> str:
        """Retorna resumo textual da evolução"""
        status_emoji = {
            "improving": "📈",
            "stable": "➡️",
            "worsening": "📉"
        }
        
        status_text = {
            "improving": "EM MELHORA",
            "stable": "ESTÁVEL",
            "worsening": "EM PIORA"
        }
        
        lines = [
            "=" * 50,
            "RELATÓRIO DE EVOLUÇÃO",
            "=" * 50,
            "",
            f"📅 Período: {self.previous.timestamp.strftime('%d/%m/%Y')} → "
            f"{self.current.timestamp.strftime('%d/%m/%Y')} ({self.days_between} dias)",
            "",
            f"{status_emoji[self.evolution_status]} Status: {status_text[self.evolution_status]}",
            "",
            "📏 VARIAÇÃO DE ÁREA:",
            f"   {self.area_change_percent:+.1f}% ({self.area_change_pixels:+,} pixels)",
        ]
        
        if self.area_change_cm2 is not None:
            lines.append(f"   {self.area_change_cm2:+.2f} cm²")
        
        lines.extend([
            "",
            "🔬 VARIAÇÃO TECIDUAL:",
        ])
        
        for tissue, change in self.tissue_changes.items():
            if abs(change) > 1:  # Só mostra mudanças significativas
                emoji = "↑" if change > 0 else "↓"
                lines.append(f"   {tissue}: {emoji} {abs(change):.1f}%")
        
        lines.extend([
            "",
            f"📊 Taxa de cicatrização: {self.healing_rate_percent_per_week:.1f}% por semana",
        ])
        
        if self.estimated_healing_weeks is not None:
            lines.append(f"⏱️ Estimativa para cicatrização: {self.estimated_healing_weeks} semanas")
        
        lines.append("=" * 50)
        
        return "\n".join(lines)


class EvolutionTracker:
    """
    Rastreador de evolução de feridas ao longo do tempo.
    
    Funcionalidades:
    - Armazenar histórico de medições
    - Calcular mudanças entre medições
    - Estimar tempo para cicatrização
    - Gerar relatórios de evolução
    """
    
    # Limiares para classificação de evolução
    IMPROVING_THRESHOLD = -5.0  # Redução > 5% = melhora
    WORSENING_THRESHOLD = 5.0   # Aumento > 5% = piora
    
    def __init__(self, patient_id: str):
        """
        Args:
            patient_id: Identificador único do paciente
        """
        self.patient_id = patient_id
        self.measurements: List[WoundMeasurement] = []
        
    def add_measurement(
        self,
        segmentation: TissueSegmentationResult,
        image_path: Optional[str] = None,
        pixels_per_cm: Optional[float] = None,
        notes: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> WoundMeasurement:
        """
        Adiciona nova medição ao histórico.
        
        Args:
            segmentation: Resultado da segmentação
            image_path: Caminho da imagem (opcional)
            pixels_per_cm: Escala para cálculo em cm²
            notes: Observações
            timestamp: Data/hora (usa atual se não fornecido)
            
        Returns:
            WoundMeasurement criada
        """
        area_cm2 = None
        if pixels_per_cm is not None:
            area_cm2 = WoundAreaCalculator.calculate_area_cm2(
                segmentation.mask,
                pixels_per_cm
            )
        
        measurement = WoundMeasurement(
            timestamp=timestamp or datetime.now(),
            image_path=image_path,
            area_pixels=segmentation.wound_area_pixels,
            area_cm2=area_cm2,
            tissue_percentages=segmentation.tissue_percentages.copy(),
            segmentation_mask=segmentation.mask.copy(),
            notes=notes
        )
        
        self.measurements.append(measurement)
        self.measurements.sort(key=lambda m: m.timestamp)
        
        logger.info(
            f"Medição adicionada para paciente {self.patient_id}: "
            f"{measurement.area_pixels} px, {len(self.measurements)} total"
        )
        
        return measurement
    
    def get_latest_evolution(self) -> Optional[EvolutionReport]:
        """Retorna evolução entre as duas últimas medições"""
        if len(self.measurements) < 2:
            return None
        
        return self.compare_measurements(
            self.measurements[-1],
            self.measurements[-2]
        )
    
    def get_evolution_from_start(self) -> Optional[EvolutionReport]:
        """Retorna evolução desde a primeira medição"""
        if len(self.measurements) < 2:
            return None
        
        return self.compare_measurements(
            self.measurements[-1],
            self.measurements[0]
        )
    
    def compare_measurements(
        self,
        current: WoundMeasurement,
        previous: WoundMeasurement
    ) -> EvolutionReport:
        """
        Compara duas medições e gera relatório de evolução.
        
        Args:
            current: Medição mais recente
            previous: Medição anterior
            
        Returns:
            EvolutionReport
        """
        # Dias entre medições
        days_between = (current.timestamp - previous.timestamp).days
        days_between = max(1, days_between)  # Mínimo 1 dia
        
        # Mudança de área
        area_change_pixels = current.area_pixels - previous.area_pixels
        
        area_change_cm2 = None
        if current.area_cm2 is not None and previous.area_cm2 is not None:
            area_change_cm2 = current.area_cm2 - previous.area_cm2
        
        # Mudança percentual
        if previous.area_pixels > 0:
            area_change_percent = (area_change_pixels / previous.area_pixels) * 100
        else:
            area_change_percent = 0.0
        
        # Mudanças de tecido
        tissue_changes = {}
        for tissue in current.tissue_percentages:
            current_pct = current.tissue_percentages.get(tissue, 0)
            previous_pct = previous.tissue_percentages.get(tissue, 0)
            tissue_changes[tissue] = current_pct - previous_pct
        
        # Classificação da evolução
        evolution_status = self._classify_evolution(
            area_change_percent,
            tissue_changes
        )
        
        # Taxa de cicatrização por semana
        healing_rate = -(area_change_percent / days_between) * 7
        
        # Estimativa de semanas para cicatrização
        estimated_weeks = None
        if healing_rate > 0 and current.area_pixels > 0:
            # Semanas = área atual / (taxa por semana * área anterior)
            weeks = 100 / healing_rate
            if weeks < 52:  # Máximo 1 ano
                estimated_weeks = int(np.ceil(weeks))
        
        return EvolutionReport(
            current=current,
            previous=previous,
            days_between=days_between,
            area_change_pixels=area_change_pixels,
            area_change_cm2=area_change_cm2,
            area_change_percent=area_change_percent,
            tissue_changes=tissue_changes,
            evolution_status=evolution_status,
            healing_rate_percent_per_week=healing_rate,
            estimated_healing_weeks=estimated_weeks
        )
    
    def _classify_evolution(
        self,
        area_change_percent: float,
        tissue_changes: Dict[str, float]
    ) -> str:
        """Classifica evolução como improving, stable ou worsening"""
        
        # Considera mudança de área
        if area_change_percent < self.IMPROVING_THRESHOLD:
            area_score = 1  # Melhora
        elif area_change_percent > self.WORSENING_THRESHOLD:
            area_score = -1  # Piora
        else:
            area_score = 0  # Estável
        
        # Considera mudança de tecido
        granulation_change = tissue_changes.get(TISSUE_NAMES[TissueType.GRANULATION.value], 0)
        necrosis_change = tissue_changes.get(TISSUE_NAMES[TissueType.NECROSIS.value], 0)
        
        tissue_score = 0
        if granulation_change > 10:  # Aumento de granulação é bom
            tissue_score += 1
        elif granulation_change < -10:
            tissue_score -= 1
            
        if necrosis_change > 5:  # Aumento de necrose é ruim
            tissue_score -= 1
        elif necrosis_change < -5:
            tissue_score += 1
        
        # Combina scores
        total_score = area_score + tissue_score
        
        if total_score > 0:
            return "improving"
        elif total_score < 0:
            return "worsening"
        else:
            return "stable"
    
    def generate_timeline_visualization(
        self,
        output_path: Optional[str] = None
    ) -> np.ndarray:
        """
        Gera visualização da evolução ao longo do tempo.
        
        Returns:
            Imagem numpy array com gráfico de evolução
        """
        if len(self.measurements) < 2:
            logger.warning("Necessário pelo menos 2 medições para visualização")
            return np.zeros((400, 800, 3), dtype=np.uint8)
        
        # Dimensões do canvas
        width, height = 800, 400
        margin = 60
        canvas = np.ones((height, width, 3), dtype=np.uint8) * 255
        
        # Área do gráfico
        graph_left = margin
        graph_right = width - margin
        graph_top = margin
        graph_bottom = height - margin
        graph_width = graph_right - graph_left
        graph_height = graph_bottom - graph_top
        
        # Dados
        areas = [m.area_pixels for m in self.measurements]
        dates = [m.timestamp for m in self.measurements]
        
        max_area = max(areas) * 1.1
        min_area = 0
        
        # Desenha eixos
        cv2.line(canvas, (graph_left, graph_bottom), (graph_right, graph_bottom), (0, 0, 0), 2)
        cv2.line(canvas, (graph_left, graph_top), (graph_left, graph_bottom), (0, 0, 0), 2)
        
        # Título
        cv2.putText(
            canvas,
            f"Evolucao da Ferida - Paciente {self.patient_id}",
            (width // 2 - 180, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 0),
            2
        )
        
        # Labels dos eixos
        cv2.putText(canvas, "Area (px)", (10, height // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        cv2.putText(canvas, "Data", (width // 2 - 20, height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        # Desenha pontos e linha
        points = []
        for i, (area, date) in enumerate(zip(areas, dates)):
            x = graph_left + int((i / (len(areas) - 1)) * graph_width) if len(areas) > 1 else graph_left + graph_width // 2
            y = graph_bottom - int(((area - min_area) / (max_area - min_area)) * graph_height)
            points.append((x, y))
            
            # Ponto
            cv2.circle(canvas, (x, y), 6, (0, 0, 255), -1)
            cv2.circle(canvas, (x, y), 6, (0, 0, 0), 1)
            
            # Data
            date_str = date.strftime("%d/%m")
            cv2.putText(canvas, date_str, (x - 15, graph_bottom + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        
        # Linha conectando pontos
        for i in range(len(points) - 1):
            cv2.line(canvas, points[i], points[i + 1], (255, 0, 0), 2)
        
        # Salva se path fornecido
        if output_path:
            cv2.imwrite(output_path, canvas)
            logger.info(f"Visualização salva em {output_path}")
        
        return canvas
    
    def get_history(self) -> List[Dict]:
        """Retorna histórico completo como lista de dicionários"""
        return [m.to_dict() for m in self.measurements]
    
    def clear_history(self):
        """Limpa histórico de medições"""
        self.measurements.clear()
        logger.info(f"Histórico do paciente {self.patient_id} limpo")
