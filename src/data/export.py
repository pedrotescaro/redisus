"""
REDISUS - Sistema de Diagnóstico de Feridas
Módulo de Exportação e Relatórios

Gera relatórios em diferentes formatos:
- PDF
- JSON
- CSV
- Imagem com anotações
"""
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import cv2
import numpy as np
from loguru import logger


@dataclass
class ReportConfig:
    """Configuração do relatório"""
    include_images: bool = True
    include_charts: bool = True
    include_recommendations: bool = True
    include_history: bool = True
    language: str = "pt-BR"
    logo_path: Optional[str] = None


class ExportManager:
    """
    Gerenciador de exportação de dados.
    
    Formatos suportados:
    - JSON: Dados estruturados
    - CSV: Planilha para Excel
    - Imagem: Visualização anotada
    """
    
    def __init__(self, output_dir: str = "output/exports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def export_analysis_json(
        self,
        analysis_data: Dict,
        filename: Optional[str] = None
    ) -> str:
        """
        Exporta análise para JSON.
        
        Args:
            analysis_data: Dados da análise
            filename: Nome do arquivo (auto-gerado se não fornecido)
            
        Returns:
            Caminho do arquivo gerado
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analysis_{timestamp}.json"
            
        filepath = self.output_dir / filename
        
        # Adiciona metadados
        export_data = {
            "export_info": {
                "version": "1.0",
                "exported_at": datetime.now().isoformat(),
                "generator": "REDISUS v1.0"
            },
            "analysis": analysis_data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Análise exportada: {filepath}")
        return str(filepath)
    
    def export_analyses_csv(
        self,
        analyses: List[Dict],
        filename: Optional[str] = None
    ) -> str:
        """
        Exporta múltiplas análises para CSV.
        
        Args:
            analyses: Lista de análises
            filename: Nome do arquivo
            
        Returns:
            Caminho do arquivo
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analyses_{timestamp}.csv"
            
        filepath = self.output_dir / filename
        
        if not analyses:
            logger.warning("Lista de análises vazia")
            return ""
            
        # Define colunas
        columns = [
            "id", "patient_id", "timestamp", "etiology", "confidence",
            "health_score", "wound_area_cm2", "granulation", "slough",
            "necrosis", "epithelialization", "notes"
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            
            for analysis in analyses:
                row = {
                    "id": analysis.get("id", ""),
                    "patient_id": analysis.get("patient_id", ""),
                    "timestamp": analysis.get("timestamp", ""),
                    "etiology": analysis.get("etiology", ""),
                    "confidence": analysis.get("confidence", 0),
                    "health_score": analysis.get("health_score", 0),
                    "wound_area_cm2": analysis.get("wound_area_cm2", ""),
                }
                
                # Extrai porcentagens de tecido
                tissue = analysis.get("tissue_percentages", {})
                row["granulation"] = tissue.get("granulation", 0)
                row["slough"] = tissue.get("slough", 0)
                row["necrosis"] = tissue.get("necrosis", 0)
                row["epithelialization"] = tissue.get("epithelialization", 0)
                row["notes"] = analysis.get("notes", "")
                
                writer.writerow(row)
                
        logger.info(f"Análises exportadas: {filepath}")
        return str(filepath)
    
    def export_annotated_image(
        self,
        image: np.ndarray,
        analysis_data: Dict,
        filename: Optional[str] = None
    ) -> str:
        """
        Exporta imagem com anotações de análise.
        
        Args:
            image: Imagem original
            analysis_data: Dados da análise
            filename: Nome do arquivo
            
        Returns:
            Caminho do arquivo
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"annotated_{timestamp}.jpg"
            
        filepath = self.output_dir / filename
        
        # Cria cópia anotada
        annotated = self._create_annotated_image(image, analysis_data)
        
        cv2.imwrite(str(filepath), annotated)
        
        logger.info(f"Imagem anotada exportada: {filepath}")
        return str(filepath)
    
    def _create_annotated_image(
        self,
        image: np.ndarray,
        analysis_data: Dict
    ) -> np.ndarray:
        """Cria imagem com anotações"""
        h, w = image.shape[:2]
        
        # Cria canvas expandido para informações
        canvas_width = w + 350
        canvas = np.zeros((h, canvas_width, 3), dtype=np.uint8)
        canvas[:] = (40, 40, 40)
        
        # Coloca imagem original
        canvas[:h, :w] = image
        
        # Painel de informações
        x_info = w + 20
        y = 30
        
        # Título
        cv2.putText(canvas, "REDISUS - ANÁLISE", (x_info, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 150), 2)
        y += 35
        
        # Data/hora
        timestamp = analysis_data.get("timestamp", datetime.now().isoformat())
        cv2.putText(canvas, f"Data: {timestamp[:16]}", (x_info, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
        y += 30
        
        # Linha separadora
        cv2.line(canvas, (x_info, y), (canvas_width - 20, y), (80, 80, 80), 1)
        y += 20
        
        # Etiologia
        etiology = analysis_data.get("etiology", "N/A")
        confidence = analysis_data.get("confidence", 0)
        
        cv2.putText(canvas, "Etiologia:", (x_info, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)
        y += 22
        cv2.putText(canvas, etiology, (x_info, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        y += 25
        cv2.putText(canvas, f"Confiança: {confidence:.1%}", (x_info, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
        y += 30
        
        # Health score
        health_score = analysis_data.get("health_score", 0)
        cv2.putText(canvas, f"Score de Saúde: {health_score:.0f}/100", (x_info, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 150), 1)
        y += 30
        
        # Linha separadora
        cv2.line(canvas, (x_info, y), (canvas_width - 20, y), (80, 80, 80), 1)
        y += 20
        
        # Tecidos
        cv2.putText(canvas, "Composição Tecidual:", (x_info, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)
        y += 25
        
        tissues = analysis_data.get("tissue_percentages", {})
        colors = {
            "granulation": (60, 60, 220),
            "slough": (80, 220, 220),
            "necrosis": (50, 50, 50),
            "epithelialization": (200, 180, 255)
        }
        
        for tissue, percentage in sorted(tissues.items(), key=lambda x: -x[1]):
            if percentage > 0.5:
                color = colors.get(tissue, (150, 150, 150))
                cv2.rectangle(canvas, (x_info, y - 10), (x_info + 15, y + 5), color, -1)
                cv2.putText(canvas, f"{tissue}: {percentage:.1f}%", (x_info + 25, y),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
                y += 20
                
        # Área
        area = analysis_data.get("wound_area_cm2")
        if area:
            y += 10
            cv2.putText(canvas, f"Área: {area:.2f} cm²", (x_info, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            y += 30
            
        # Linha separadora
        cv2.line(canvas, (x_info, y), (canvas_width - 20, y), (80, 80, 80), 1)
        y += 20
        
        # Aviso se precisa revisão
        if analysis_data.get("needs_review", False):
            cv2.putText(canvas, "⚠ Requer revisão", (x_info, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
            
        return canvas


class ReportGenerator:
    """
    Gerador de relatórios completos.
    
    Gera relatórios formatados com:
    - Resumo da análise
    - Imagens anotadas
    - Histórico de evolução
    - Recomendações de tratamento
    """
    
    def __init__(self, config: Optional[ReportConfig] = None):
        self.config = config or ReportConfig()
        self.export_manager = ExportManager()
        
    def generate_analysis_report(
        self,
        analysis_data: Dict,
        image: Optional[np.ndarray] = None,
        output_dir: str = "output/reports"
    ) -> Dict[str, str]:
        """
        Gera relatório completo de análise.
        
        Args:
            analysis_data: Dados da análise
            image: Imagem (opcional)
            output_dir: Diretório de saída
            
        Returns:
            Dict com caminhos dos arquivos gerados
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        patient_id = analysis_data.get("patient_id", "unknown")
        base_name = f"report_{patient_id}_{timestamp}"
        
        generated_files = {}
        
        # JSON
        json_path = output_path / f"{base_name}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            report_data = self._create_report_data(analysis_data)
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        generated_files["json"] = str(json_path)
        
        # Imagem anotada
        if image is not None and self.config.include_images:
            img_path = output_path / f"{base_name}.jpg"
            annotated = self.export_manager._create_annotated_image(image, analysis_data)
            cv2.imwrite(str(img_path), annotated)
            generated_files["image"] = str(img_path)
            
        # Texto formatado
        txt_path = output_path / f"{base_name}.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(self._create_text_report(analysis_data))
        generated_files["text"] = str(txt_path)
        
        logger.info(f"Relatório gerado: {output_path / base_name}")
        return generated_files
    
    def _create_report_data(self, analysis_data: Dict) -> Dict:
        """Cria estrutura de dados do relatório"""
        return {
            "report": {
                "title": "Relatório de Análise de Ferida",
                "generated_at": datetime.now().isoformat(),
                "version": "1.0",
                "generator": "REDISUS - Sistema de Diagnóstico de Feridas"
            },
            "patient": {
                "id": analysis_data.get("patient_id", "N/A"),
                "name": analysis_data.get("patient_name", "N/A")
            },
            "analysis": {
                "id": analysis_data.get("id", ""),
                "timestamp": analysis_data.get("timestamp", ""),
                "etiology": {
                    "type": analysis_data.get("etiology", "unknown"),
                    "confidence": analysis_data.get("confidence", 0),
                    "needs_review": analysis_data.get("needs_review", False)
                },
                "tissue_composition": analysis_data.get("tissue_percentages", {}),
                "measurements": {
                    "area_cm2": analysis_data.get("wound_area_cm2"),
                    "health_score": analysis_data.get("health_score", 0)
                }
            },
            "recommendations": analysis_data.get("recommendations", []),
            "notes": analysis_data.get("notes", "")
        }
    
    def _create_text_report(self, analysis_data: Dict) -> str:
        """Cria relatório em texto formatado"""
        lines = [
            "=" * 60,
            "REDISUS - RELATÓRIO DE ANÁLISE DE FERIDA",
            "=" * 60,
            "",
            f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            f"ID da Análise: {analysis_data.get('id', 'N/A')}",
            f"Paciente: {analysis_data.get('patient_id', 'N/A')}",
            "",
            "-" * 60,
            "DIAGNÓSTICO",
            "-" * 60,
            "",
            f"Etiologia: {analysis_data.get('etiology', 'Não identificado')}",
            f"Confiança: {analysis_data.get('confidence', 0):.1%}",
            f"Score de Saúde: {analysis_data.get('health_score', 0):.0f}/100",
            "",
        ]
        
        # Área
        area = analysis_data.get("wound_area_cm2")
        if area:
            lines.append(f"Área da Ferida: {area:.2f} cm²")
            lines.append("")
            
        # Composição tecidual
        lines.extend([
            "-" * 60,
            "COMPOSIÇÃO TECIDUAL",
            "-" * 60,
            ""
        ])
        
        tissues = analysis_data.get("tissue_percentages", {})
        for tissue, percentage in sorted(tissues.items(), key=lambda x: -x[1]):
            if percentage > 0.5:
                bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
                lines.append(f"  {tissue:20} [{bar}] {percentage:.1f}%")
                
        lines.append("")
        
        # Recomendações
        recommendations = analysis_data.get("recommendations", [])
        if recommendations and self.config.include_recommendations:
            lines.extend([
                "-" * 60,
                "RECOMENDAÇÕES",
                "-" * 60,
                ""
            ])
            for i, rec in enumerate(recommendations, 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")
            
        # Notas
        notes = analysis_data.get("notes", "")
        if notes:
            lines.extend([
                "-" * 60,
                "OBSERVAÇÕES",
                "-" * 60,
                "",
                f"  {notes}",
                ""
            ])
            
        # Aviso
        if analysis_data.get("needs_review", False):
            lines.extend([
                "",
                "⚠ ATENÇÃO: Esta análise requer revisão por especialista.",
                ""
            ])
            
        lines.extend([
            "=" * 60,
            "Relatório gerado automaticamente pelo REDISUS",
            "Este documento não substitui avaliação profissional",
            "=" * 60
        ])
        
        return "\n".join(lines)
    
    def generate_evolution_report(
        self,
        analyses: List[Dict],
        patient_info: Dict,
        output_dir: str = "output/reports"
    ) -> str:
        """
        Gera relatório de evolução do paciente.
        
        Args:
            analyses: Lista de análises ordenadas por data
            patient_info: Informações do paciente
            output_dir: Diretório de saída
            
        Returns:
            Caminho do arquivo gerado
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        patient_id = patient_info.get("id", "unknown")
        filepath = output_path / f"evolution_{patient_id}_{timestamp}.txt"
        
        lines = [
            "=" * 70,
            "REDISUS - RELATÓRIO DE EVOLUÇÃO",
            "=" * 70,
            "",
            f"Paciente: {patient_info.get('name', 'N/A')}",
            f"ID: {patient_info.get('id', 'N/A')}",
            f"Período: {analyses[-1].get('timestamp', '')[:10]} a {analyses[0].get('timestamp', '')[:10]}",
            f"Total de Análises: {len(analyses)}",
            "",
            "-" * 70,
            "HISTÓRICO DE ANÁLISES",
            "-" * 70,
            ""
        ]
        
        for i, analysis in enumerate(analyses):
            lines.extend([
                f"Análise #{len(analyses) - i}",
                f"  Data: {analysis.get('timestamp', '')[:16]}",
                f"  Etiologia: {analysis.get('etiology', 'N/A')}",
                f"  Health Score: {analysis.get('health_score', 0):.0f}/100",
                ""
            ])
            
        # Comparação início vs fim
        if len(analyses) >= 2:
            first = analyses[-1]
            last = analyses[0]
            
            score_change = last.get("health_score", 0) - first.get("health_score", 0)
            
            lines.extend([
                "-" * 70,
                "COMPARATIVO",
                "-" * 70,
                "",
                f"Health Score Inicial: {first.get('health_score', 0):.0f}",
                f"Health Score Atual: {last.get('health_score', 0):.0f}",
                f"Variação: {'+' if score_change >= 0 else ''}{score_change:.0f}",
                ""
            ])
            
            if score_change > 10:
                lines.append("✓ EVOLUÇÃO POSITIVA: Melhora significativa observada")
            elif score_change > 0:
                lines.append("→ Leve melhora observada")
            elif score_change > -10:
                lines.append("→ Condição estável")
            else:
                lines.append("⚠ ATENÇÃO: Piora observada, avaliar intervenções")
                
        lines.extend([
            "",
            "=" * 70,
            "Relatório gerado pelo REDISUS",
            "=" * 70
        ])
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
            
        logger.info(f"Relatório de evolução gerado: {filepath}")
        return str(filepath)
