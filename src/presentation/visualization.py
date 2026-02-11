"""
REDISUS - Sistema de Diagnóstico de Feridas
Módulo de Visualização Avançada

Implementa visualizações especializadas para análise de feridas:
- Mapas de calor (heatmaps)
- Segmentação colorida
- Overlays de tecido
- Comparações lado-a-lado
"""
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ColorMapType(Enum):
    """Tipos de mapas de cores"""
    JET = "jet"
    VIRIDIS = "viridis"
    MEDICAL = "medical"
    TISSUE = "tissue"


@dataclass
class ColorMaps:
    """Mapas de cores para visualização"""
    
    # Cores de tecidos (BGR)
    TISSUE = {
        "background": (128, 128, 128),
        "granulation": (60, 60, 220),      # Vermelho vivo
        "slough": (80, 220, 220),          # Amarelo
        "necrosis": (40, 40, 40),          # Preto/escuro
        "periwound": (80, 200, 80),        # Verde
        "epithelialization": (255, 200, 150),  # Rosa claro
        "fibrin": (150, 200, 255),         # Amarelo claro
        "eschar": (20, 20, 60),            # Marrom escuro
    }
    
    # Cores de etiologias (BGR)
    ETIOLOGY = {
        "venous_ulcer": (200, 120, 50),
        "arterial_ulcer": (50, 80, 200),
        "diabetic_foot": (50, 180, 230),
        "pressure_injury": (180, 80, 180),
        "surgical_wound": (80, 200, 80),
        "traumatic": (100, 150, 200),
        "burn": (50, 100, 255),
        "unknown": (128, 128, 128),
    }
    
    # Cores para severidade
    SEVERITY = {
        "mild": (80, 200, 80),      # Verde
        "moderate": (0, 200, 255),   # Amarelo
        "severe": (0, 100, 255),     # Laranja
        "critical": (0, 0, 255),     # Vermelho
    }
    
    @staticmethod
    def get_tissue_color(tissue_name: str) -> Tuple[int, int, int]:
        """Retorna cor BGR para um tipo de tecido"""
        return ColorMaps.TISSUE.get(tissue_name.lower(), (128, 128, 128))
    
    @staticmethod
    def get_etiology_color(etiology_name: str) -> Tuple[int, int, int]:
        """Retorna cor BGR para uma etiologia"""
        return ColorMaps.ETIOLOGY.get(etiology_name.lower(), (128, 128, 128))


class WoundVisualization:
    """
    Visualizações especializadas para análise de feridas.
    
    Métodos principais:
    - create_tissue_overlay: Sobrepõe máscara de tecidos colorida
    - create_heatmap: Gera mapa de calor de atividade
    - create_comparison: Comparação lado-a-lado
    - create_dashboard: Dashboard completo de análise
    """
    
    def __init__(self):
        self.colors = ColorMaps()
        
    def create_tissue_overlay(
        self,
        image: np.ndarray,
        tissue_mask: np.ndarray,
        alpha: float = 0.5,
        show_legend: bool = True
    ) -> np.ndarray:
        """
        Cria overlay colorido de segmentação de tecidos.
        
        Args:
            image: Imagem original (BGR)
            tissue_mask: Máscara de segmentação (H, W) com IDs de classe
            alpha: Transparência do overlay (0-1)
            show_legend: Se deve mostrar legenda
            
        Returns:
            Imagem com overlay de tecidos
        """
        output = image.copy()
        h, w = image.shape[:2]
        
        # Mapeia IDs para cores
        tissue_names = ["background", "granulation", "slough", "necrosis", "periwound"]
        
        # Cria máscara colorida
        color_mask = np.zeros((h, w, 3), dtype=np.uint8)
        
        for tissue_id, tissue_name in enumerate(tissue_names):
            mask = tissue_mask == tissue_id
            color = self.colors.get_tissue_color(tissue_name)
            color_mask[mask] = color
            
        # Aplica overlay com transparência
        cv2.addWeighted(color_mask, alpha, output, 1 - alpha, 0, output)
        
        # Adiciona legenda
        if show_legend:
            output = self._draw_tissue_legend(output, tissue_names, tissue_mask)
            
        return output
    
    def create_heatmap(
        self,
        image: np.ndarray,
        activity_map: np.ndarray,
        colormap: int = cv2.COLORMAP_JET,
        alpha: float = 0.6
    ) -> np.ndarray:
        """
        Cria mapa de calor sobre a imagem.
        
        Args:
            image: Imagem original
            activity_map: Mapa de atividade (0-255)
            colormap: Tipo de colormap do OpenCV
            alpha: Transparência
            
        Returns:
            Imagem com heatmap
        """
        output = image.copy()
        
        # Normaliza e aplica colormap
        if activity_map.dtype != np.uint8:
            activity_map = (activity_map * 255).astype(np.uint8)
            
        heatmap = cv2.applyColorMap(activity_map, colormap)
        
        # Resize se necessário
        if heatmap.shape[:2] != image.shape[:2]:
            heatmap = cv2.resize(heatmap, (image.shape[1], image.shape[0]))
            
        # Blend
        cv2.addWeighted(heatmap, alpha, output, 1 - alpha, 0, output)
        
        return output
    
    def create_comparison(
        self,
        image1: np.ndarray,
        image2: np.ndarray,
        labels: Tuple[str, str] = ("Antes", "Depois"),
        orientation: str = "horizontal"
    ) -> np.ndarray:
        """
        Cria comparação lado-a-lado de duas imagens.
        
        Args:
            image1: Primeira imagem
            image2: Segunda imagem
            labels: Rótulos para as imagens
            orientation: "horizontal" ou "vertical"
            
        Returns:
            Imagem combinada
        """
        # Garante mesmo tamanho
        h1, w1 = image1.shape[:2]
        h2, w2 = image2.shape[:2]
        
        if orientation == "horizontal":
            # Ajusta altura
            target_h = max(h1, h2)
            if h1 != target_h:
                image1 = cv2.resize(image1, (int(w1 * target_h / h1), target_h))
            if h2 != target_h:
                image2 = cv2.resize(image2, (int(w2 * target_h / h2), target_h))
                
            # Concatena horizontalmente
            combined = np.hstack([image1, image2])
            
            # Labels
            cv2.putText(combined, labels[0], (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(combined, labels[1], (image1.shape[1] + 20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            # Linha divisória
            cv2.line(combined, (image1.shape[1], 0), (image1.shape[1], target_h), (255, 255, 255), 2)
            
        else:
            # Ajusta largura
            target_w = max(w1, w2)
            if w1 != target_w:
                image1 = cv2.resize(image1, (target_w, int(h1 * target_w / w1)))
            if w2 != target_w:
                image2 = cv2.resize(image2, (target_w, int(h2 * target_w / w2)))
                
            # Concatena verticalmente
            combined = np.vstack([image1, image2])
            
            # Labels
            cv2.putText(combined, labels[0], (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(combined, labels[1], (20, image1.shape[0] + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            # Linha divisória
            cv2.line(combined, (0, image1.shape[0]), (target_w, image1.shape[0]), (255, 255, 255), 2)
            
        return combined
    
    def create_dashboard(
        self,
        original: np.ndarray,
        segmentation: np.ndarray,
        analysis_result: Dict,
        size: Tuple[int, int] = (1280, 720)
    ) -> np.ndarray:
        """
        Cria dashboard completo de análise.
        
        Layout:
        ┌─────────────────┬─────────────────┐
        │                 │   Segmentação   │
        │    Original     ├─────────────────┤
        │                 │   Resultados    │
        └─────────────────┴─────────────────┘
        
        Args:
            original: Imagem original
            segmentation: Máscara de segmentação
            analysis_result: Resultado da análise
            size: Tamanho do dashboard
            
        Returns:
            Dashboard completo
        """
        w, h = size
        half_w = w // 2
        half_h = h // 2
        
        # Canvas
        dashboard = np.zeros((h, w, 3), dtype=np.uint8)
        dashboard[:] = (30, 30, 30)  # Background
        
        # Redimensiona original para metade esquerda
        original_resized = cv2.resize(original, (half_w - 20, h - 20))
        dashboard[10:h-10, 10:half_w-10] = original_resized
        
        # Cria overlay de segmentação
        seg_overlay = self.create_tissue_overlay(original, segmentation, show_legend=False)
        seg_resized = cv2.resize(seg_overlay, (half_w - 20, half_h - 20))
        dashboard[10:half_h-10, half_w+10:w-10] = seg_resized
        
        # Painel de resultados (quadrante inferior direito)
        result_panel = self._create_result_panel(
            size=(half_w - 20, half_h - 20),
            analysis_result=analysis_result
        )
        dashboard[half_h+10:h-10, half_w+10:w-10] = result_panel
        
        # Títulos
        cv2.putText(dashboard, "IMAGEM ORIGINAL", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        cv2.putText(dashboard, "SEGMENTAÇÃO", (half_w + 20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        cv2.putText(dashboard, "ANÁLISE", (half_w + 20, half_h + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        
        # Bordas
        cv2.rectangle(dashboard, (5, 5), (half_w - 5, h - 5), (60, 60, 60), 1)
        cv2.rectangle(dashboard, (half_w + 5, 5), (w - 5, half_h - 5), (60, 60, 60), 1)
        cv2.rectangle(dashboard, (half_w + 5, half_h + 5), (w - 5, h - 5), (60, 60, 60), 1)
        
        return dashboard
    
    def draw_wound_contour(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2,
        fill: bool = False,
        fill_alpha: float = 0.3
    ) -> np.ndarray:
        """
        Desenha contorno da ferida baseado em máscara.
        
        Args:
            image: Imagem original
            mask: Máscara binária da ferida
            color: Cor do contorno
            thickness: Espessura da linha
            fill: Se deve preencher a área
            fill_alpha: Transparência do preenchimento
            
        Returns:
            Imagem com contorno
        """
        output = image.copy()
        
        # Garante máscara binária
        if mask.dtype != np.uint8:
            mask = (mask > 0).astype(np.uint8) * 255
            
        # Encontra contornos
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if fill:
            # Preenche com transparência
            overlay = output.copy()
            cv2.drawContours(overlay, contours, -1, color, -1)
            cv2.addWeighted(overlay, fill_alpha, output, 1 - fill_alpha, 0, output)
            
        # Desenha contorno
        cv2.drawContours(output, contours, -1, color, thickness)
        
        return output
    
    def draw_measurement_overlay(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        pixels_per_cm: float = 50.0
    ) -> np.ndarray:
        """
        Desenha overlay com medições da ferida.
        
        Args:
            image: Imagem original
            mask: Máscara da ferida
            pixels_per_cm: Fator de conversão
            
        Returns:
            Imagem com medições
        """
        output = image.copy()
        
        # Encontra contornos
        if mask.dtype != np.uint8:
            mask = (mask > 0).astype(np.uint8) * 255
            
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return output
            
        # Pega maior contorno
        largest = max(contours, key=cv2.contourArea)
        
        # Bounding box rotacionado
        rect = cv2.minAreaRect(largest)
        box = cv2.boxPoints(rect)
        box = np.int32(box)
        
        # Desenha bounding box
        cv2.drawContours(output, [box], 0, (0, 255, 255), 2)
        
        # Calcula dimensões
        width_px = rect[1][0]
        height_px = rect[1][1]
        width_cm = width_px / pixels_per_cm
        height_cm = height_px / pixels_per_cm
        
        # Área
        area_px = cv2.contourArea(largest)
        area_cm2 = area_px / (pixels_per_cm ** 2)
        
        # Perímetro
        perimeter_px = cv2.arcLength(largest, True)
        perimeter_cm = perimeter_px / pixels_per_cm
        
        # Textos
        center = (int(rect[0][0]), int(rect[0][1]))
        
        cv2.putText(
            output,
            f"{width_cm:.1f} x {height_cm:.1f} cm",
            (center[0] - 60, center[1] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2
        )
        
        cv2.putText(
            output,
            f"Área: {area_cm2:.2f} cm²",
            (center[0] - 50, center[1] + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1
        )
        
        return output
    
    def _draw_tissue_legend(
        self,
        image: np.ndarray,
        tissue_names: List[str],
        tissue_mask: np.ndarray
    ) -> np.ndarray:
        """Desenha legenda de tecidos"""
        output = image.copy()
        h, w = image.shape[:2]
        
        # Calcula porcentagens
        total = tissue_mask.size
        percentages = {}
        for i, name in enumerate(tissue_names):
            count = np.sum(tissue_mask == i)
            percentages[name] = (count / total) * 100
            
        # Background da legenda
        legend_h = len(tissue_names) * 25 + 30
        legend_w = 180
        legend_x = w - legend_w - 20
        legend_y = h - legend_h - 20
        
        overlay = output.copy()
        cv2.rectangle(overlay, (legend_x, legend_y), (w - 20, h - 20), (40, 40, 40), -1)
        cv2.addWeighted(overlay, 0.8, output, 0.2, 0, output)
        
        # Título
        cv2.putText(output, "TECIDOS", (legend_x + 10, legend_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        # Itens
        y = legend_y + 40
        for name in tissue_names:
            if percentages[name] > 0.5:  # Só mostra se > 0.5%
                color = self.colors.get_tissue_color(name)
                
                # Quadrado colorido
                cv2.rectangle(output, (legend_x + 10, y - 10), (legend_x + 25, y + 5), color, -1)
                
                # Texto
                cv2.putText(
                    output,
                    f"{name}: {percentages[name]:.1f}%",
                    (legend_x + 35, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (200, 200, 200),
                    1
                )
                
                y += 20
                
        return output
    
    def _create_result_panel(
        self,
        size: Tuple[int, int],
        analysis_result: Dict
    ) -> np.ndarray:
        """Cria painel de resultados"""
        w, h = size
        panel = np.zeros((h, w, 3), dtype=np.uint8)
        panel[:] = (35, 35, 35)
        
        y = 30
        
        # Etiologia
        etiology = analysis_result.get("etiology", "Não identificado")
        confidence = analysis_result.get("confidence", 0)
        
        cv2.putText(panel, "Etiologia:", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)
        y += 25
        cv2.putText(panel, etiology, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 150), 1)
        y += 30
        
        # Confiança
        cv2.putText(panel, f"Confiança: {confidence:.1%}", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        y += 30
        
        # Tecidos
        if "tissue_percentages" in analysis_result:
            cv2.putText(panel, "Composição:", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)
            y += 20
            
            for tissue, pct in analysis_result["tissue_percentages"].items():
                if pct > 1:
                    color = self.colors.get_tissue_color(tissue)
                    cv2.rectangle(panel, (20, y - 8), (35, y + 5), color, -1)
                    cv2.putText(panel, f"{tissue}: {pct:.1f}%", (45, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
                    y += 18
                    
        # Área
        if "area_cm2" in analysis_result:
            y += 10
            cv2.putText(panel, f"Área: {analysis_result['area_cm2']:.2f} cm²", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            
        return panel
