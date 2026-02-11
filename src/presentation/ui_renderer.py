"""
REDISUS - Sistema de Diagnostico de Feridas
Modulo de Renderizacao de Interface (UI)

Este modulo implementa uma interface visual moderna usando OpenCV,
com HUD informativo, overlays de analise e visualizacao em tempo real.

Nota: Usa renderizador de texto ASCII para evitar problemas de encoding.
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import cv2
import numpy as np
from loguru import logger

# Importa renderizador de texto seguro
try:
    from ..utils.text_renderer import SafeTextRenderer, to_ascii
    _text_renderer = SafeTextRenderer(use_unicode=False)
except ImportError:
    _text_renderer = None
    def to_ascii(text):
        """Fallback simples para ASCII"""
        return text.encode('ascii', 'replace').decode('ascii')


def safe_putText(
    img: np.ndarray,
    text: str,
    org: Tuple[int, int],
    fontFace: int,
    fontScale: float,
    color: Tuple[int, int, int],
    thickness: int = 1,
    lineType: int = cv2.LINE_AA
) -> None:
    """Wrapper seguro para cv2.putText que converte texto para ASCII"""
    safe_text = to_ascii(text)
    cv2.putText(img, safe_text, org, fontFace, fontScale, color, thickness, lineType)


class UITheme(Enum):
    """Temas de cores para a interface"""
    DARK = "dark"
    LIGHT = "light"
    MEDICAL = "medical"


@dataclass
class ThemeColors:
    """Paleta de cores do tema"""
    background: Tuple[int, int, int] = (30, 30, 30)
    foreground: Tuple[int, int, int] = (255, 255, 255)
    accent: Tuple[int, int, int] = (0, 200, 100)
    warning: Tuple[int, int, int] = (0, 165, 255)
    danger: Tuple[int, int, int] = (0, 0, 255)
    success: Tuple[int, int, int] = (0, 255, 0)
    info: Tuple[int, int, int] = (255, 200, 0)
    panel_bg: Tuple[int, int, int] = (40, 40, 40)
    panel_border: Tuple[int, int, int] = (80, 80, 80)
    text_primary: Tuple[int, int, int] = (255, 255, 255)
    text_secondary: Tuple[int, int, int] = (180, 180, 180)
    text_muted: Tuple[int, int, int] = (120, 120, 120)


# Temas predefinidos
THEMES = {
    UITheme.DARK: ThemeColors(),
    UITheme.LIGHT: ThemeColors(
        background=(240, 240, 240),
        foreground=(30, 30, 30),
        panel_bg=(220, 220, 220),
        panel_border=(180, 180, 180),
        text_primary=(30, 30, 30),
        text_secondary=(80, 80, 80),
        text_muted=(130, 130, 130)
    ),
    UITheme.MEDICAL: ThemeColors(
        background=(20, 40, 50),
        accent=(0, 200, 150),
        panel_bg=(30, 50, 60),
        panel_border=(50, 80, 90),
        info=(255, 220, 100)
    )
}


@dataclass
class HUDElement:
    """Elemento de HUD para exibição"""
    label: str
    value: Any
    icon: str = ""
    color: Optional[Tuple[int, int, int]] = None
    format_spec: str = ""


class HUDPanel:
    """
    Painel de HUD (Heads-Up Display) para informações em tempo real.
    
    Exibe métricas, status e informações do sistema de forma
    elegante e não intrusiva sobre o vídeo.
    """
    
    def __init__(
        self,
        position: str = "top-right",
        theme: UITheme = UITheme.DARK,
        opacity: float = 0.85
    ):
        """
        Args:
            position: Posição do painel ("top-right", "top-left", "bottom-right", "bottom-left")
            theme: Tema de cores
            opacity: Opacidade do painel (0-1)
        """
        self.position = position
        self.theme = THEMES.get(theme, THEMES[UITheme.DARK])
        self.opacity = opacity
        
        self._elements: List[HUDElement] = []
        self._title = "REDISUS"
        self._subtitle = "Sistema de Diagnóstico de Feridas"
        
        # Fontes
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_scale_title = 0.7
        self.font_scale_value = 0.55
        self.font_scale_label = 0.45
        self.thickness = 1
        
    def set_title(self, title: str, subtitle: str = ""):
        """Define título do painel"""
        self._title = title
        self._subtitle = subtitle
        
    def update_elements(self, elements: List[HUDElement]):
        """Atualiza elementos do HUD"""
        self._elements = elements
        
    def add_element(self, label: str, value: Any, icon: str = "", color: Optional[Tuple[int, int, int]] = None):
        """Adiciona um elemento ao HUD"""
        self._elements.append(HUDElement(label=label, value=value, icon=icon, color=color))
        
    def clear(self):
        """Limpa elementos"""
        self._elements.clear()
        
    def render(self, frame: np.ndarray) -> np.ndarray:
        """
        Renderiza o painel HUD sobre o frame.
        
        Args:
            frame: Frame de vídeo
            
        Returns:
            Frame com HUD renderizado
        """
        if not self._elements and not self._title:
            return frame
            
        h, w = frame.shape[:2]
        output = frame.copy()
        
        # Calcula dimensões do painel
        padding = 15
        line_height = 25
        panel_width = 280
        panel_height = (
            padding * 2 +  # Padding superior e inferior
            35 +  # Título
            (20 if self._subtitle else 0) +  # Subtítulo
            len(self._elements) * line_height +  # Elementos
            10  # Espaço extra
        )
        
        # Posição do painel
        if "right" in self.position:
            x = w - panel_width - 15
        else:
            x = 15
            
        if "top" in self.position:
            y = 15
        else:
            y = h - panel_height - 15
            
        # Desenha painel com transparência
        overlay = output.copy()
        
        # Background com gradiente suave (simulado)
        cv2.rectangle(
            overlay,
            (x, y),
            (x + panel_width, y + panel_height),
            self.theme.panel_bg,
            -1
        )
        
        # Borda
        cv2.rectangle(
            overlay,
            (x, y),
            (x + panel_width, y + panel_height),
            self.theme.panel_border,
            1
        )
        
        # Linha de destaque no topo
        cv2.line(
            overlay,
            (x, y),
            (x + panel_width, y),
            self.theme.accent,
            2
        )
        
        # Aplica transparência
        cv2.addWeighted(overlay, self.opacity, output, 1 - self.opacity, 0, output)
        
        # Renderiza conteúdo
        current_y = y + padding
        
        # Título
        safe_putText(
            output,
            self._title,
            (x + padding, current_y + 15),
            self.font,
            self.font_scale_title,
            self.theme.accent,
            self.thickness + 1
        )
        current_y += 25
        
        # Subtítulo
        if self._subtitle:
            safe_putText(
                output,
                self._subtitle,
                (x + padding, current_y + 10),
                self.font,
                self.font_scale_label,
                self.theme.text_secondary,
                self.thickness
            )
            current_y += 20
            current_y += 20
            
        # Linha separadora
        current_y += 5
        cv2.line(
            output,
            (x + padding, current_y),
            (x + panel_width - padding, current_y),
            self.theme.panel_border,
            1
        )
        current_y += 10
        
        # Elementos
        for element in self._elements:
            color = element.color or self.theme.text_primary
            
            # Label
            safe_putText(
                output,
                f"{element.icon} {element.label}:" if element.icon else f"{element.label}:",
                (x + padding, current_y + 12),
                self.font,
                self.font_scale_label,
                self.theme.text_muted,
                self.thickness
            )
            
            # Valor
            value_str = str(element.value)
            if element.format_spec:
                try:
                    value_str = format(element.value, element.format_spec)
                except:
                    pass
                    
            # Posicao do valor (alinhado a direita)
            safe_value = to_ascii(value_str)
            (text_w, _), _ = cv2.getTextSize(safe_value, self.font, self.font_scale_value, self.thickness)
            safe_putText(
                output,
                value_str,
                (x + panel_width - padding - text_w, current_y + 12),
                self.font,
                self.font_scale_value,
                color,
                self.thickness
            )
            
            current_y += line_height
            
        return output


class AnalysisOverlay:
    """
    Overlay de análise para exibir resultados sobre a ferida detectada.
    
    Renderiza:
    - Bounding boxes com estilo
    - Labels com confiança
    - Indicadores de tecido
    - Barras de progresso
    """
    
    def __init__(self, theme: UITheme = UITheme.DARK):
        self.theme = THEMES.get(theme, THEMES[UITheme.DARK])
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Cores para diferentes tipos de ferida
        self.wound_colors = {
            "venous_ulcer": (180, 100, 50),      # Azul escuro
            "arterial_ulcer": (80, 80, 200),     # Vermelho
            "diabetic_foot": (50, 150, 200),     # Laranja
            "pressure_injury": (150, 50, 150),   # Roxo
            "surgical_wound": (50, 180, 50),     # Verde
            "wound": (0, 200, 100),              # Verde claro (genérico)
            "unknown": (128, 128, 128)           # Cinza
        }
        
        # Cores para tecidos
        self.tissue_colors = {
            "granulation": (60, 60, 220),    # Vermelho (BGR)
            "slough": (80, 220, 220),        # Amarelo
            "necrosis": (50, 50, 50),        # Preto/escuro
            "periwound": (80, 200, 80),      # Verde
            "background": (128, 128, 128)    # Cinza
        }
        
    def draw_detection_box(
        self,
        frame: np.ndarray,
        bbox: Tuple[int, int, int, int],
        label: str = "Ferida",
        confidence: float = 0.0,
        wound_type: str = "wound",
        thickness: int = 2
    ) -> np.ndarray:
        """
        Desenha bounding box estilizada.
        
        Args:
            frame: Frame de vídeo
            bbox: (x1, y1, x2, y2)
            label: Texto do label
            confidence: Confiança (0-1)
            wound_type: Tipo de ferida para cor
            thickness: Espessura da linha
            
        Returns:
            Frame com bounding box
        """
        output = frame.copy()
        x1, y1, x2, y2 = bbox
        color = self.wound_colors.get(wound_type, self.wound_colors["wound"])
        
        # Box principal
        cv2.rectangle(output, (x1, y1), (x2, y2), color, thickness)
        
        # Cantos estilizados
        corner_length = min(30, (x2 - x1) // 4, (y2 - y1) // 4)
        corner_thickness = thickness + 1
        
        # Top-left
        cv2.line(output, (x1, y1), (x1 + corner_length, y1), color, corner_thickness)
        cv2.line(output, (x1, y1), (x1, y1 + corner_length), color, corner_thickness)
        
        # Top-right
        cv2.line(output, (x2, y1), (x2 - corner_length, y1), color, corner_thickness)
        cv2.line(output, (x2, y1), (x2, y1 + corner_length), color, corner_thickness)
        
        # Bottom-left
        cv2.line(output, (x1, y2), (x1 + corner_length, y2), color, corner_thickness)
        cv2.line(output, (x1, y2), (x1, y2 - corner_length), color, corner_thickness)
        
        # Bottom-right
        cv2.line(output, (x2, y2), (x2 - corner_length, y2), color, corner_thickness)
        cv2.line(output, (x2, y2), (x2, y2 - corner_length), color, corner_thickness)
        
        # Label background
        label_text = f"{label}"
        if confidence > 0:
            label_text += f" {confidence:.0%}"
            
        (text_w, text_h), baseline = cv2.getTextSize(
            label_text, self.font, 0.6, 1
        )
        
        label_y = y1 - 10 if y1 > 30 else y2 + 25
        label_x = x1
        
        # Background do label
        cv2.rectangle(
            output,
            (label_x, label_y - text_h - 8),
            (label_x + text_w + 10, label_y + 5),
            color,
            -1
        )
        
        # Texto do label
        cv2.putText(
            output,
            label_text,
            (label_x + 5, label_y - 2),
            self.font,
            0.6,
            (255, 255, 255),
            1
        )
        
        return output
        
    def draw_tissue_distribution(
        self,
        frame: np.ndarray,
        tissue_percentages: Dict[str, float],
        position: Tuple[int, int] = (20, 20),
        bar_width: int = 200
    ) -> np.ndarray:
        """
        Desenha barras de distribuição de tecidos.
        
        Args:
            frame: Frame de vídeo
            tissue_percentages: Dict com porcentagens por tecido
            position: Posição (x, y)
            bar_width: Largura das barras
            
        Returns:
            Frame com gráfico
        """
        output = frame.copy()
        x, y = position
        bar_height = 20
        padding = 5
        
        # Background do painel
        panel_height = len(tissue_percentages) * (bar_height + padding) + 40
        overlay = output.copy()
        cv2.rectangle(
            overlay,
            (x - 10, y - 10),
            (x + bar_width + 80, y + panel_height),
            self.theme.panel_bg,
            -1
        )
        cv2.addWeighted(overlay, 0.8, output, 0.2, 0, output)
        
        # Título
        cv2.putText(
            output,
            "Composição Tecidual",
            (x, y + 15),
            self.font,
            0.5,
            self.theme.text_primary,
            1
        )
        y += 30
        
        # Barras de tecido
        for tissue_name, percentage in sorted(
            tissue_percentages.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            if percentage < 0.5:  # Ignora tecidos com menos de 0.5%
                continue
                
            color = self.tissue_colors.get(tissue_name.lower(), (128, 128, 128))
            
            # Background da barra
            cv2.rectangle(
                output,
                (x, y),
                (x + bar_width, y + bar_height),
                (60, 60, 60),
                -1
            )
            
            # Barra preenchida
            fill_width = int(bar_width * percentage / 100)
            cv2.rectangle(
                output,
                (x, y),
                (x + fill_width, y + bar_height),
                color,
                -1
            )
            
            # Label e porcentagem
            cv2.putText(
                output,
                f"{tissue_name[:10]}",
                (x + 5, y + 14),
                self.font,
                0.4,
                (255, 255, 255),
                1
            )
            cv2.putText(
                output,
                f"{percentage:.1f}%",
                (x + bar_width + 5, y + 14),
                self.font,
                0.4,
                self.theme.text_primary,
                1
            )
            
            y += bar_height + padding
            
        return output
        
    def draw_confidence_meter(
        self,
        frame: np.ndarray,
        confidence: float,
        position: Tuple[int, int] = (20, 20),
        label: str = "Confiança"
    ) -> np.ndarray:
        """
        Desenha medidor de confiança circular.
        
        Args:
            frame: Frame
            confidence: Valor 0-1
            position: Centro do medidor
            label: Texto do label
            
        Returns:
            Frame com medidor
        """
        output = frame.copy()
        x, y = position
        radius = 40
        
        # Cor baseada na confiança
        if confidence >= 0.8:
            color = self.theme.success
        elif confidence >= 0.6:
            color = self.theme.warning
        else:
            color = self.theme.danger
            
        # Arco de fundo
        cv2.ellipse(
            output,
            (x, y),
            (radius, radius),
            -90,
            0,
            360,
            (60, 60, 60),
            6
        )
        
        # Arco de progresso
        angle = int(360 * confidence)
        cv2.ellipse(
            output,
            (x, y),
            (radius, radius),
            -90,
            0,
            angle,
            color,
            6
        )
        
        # Texto central
        cv2.putText(
            output,
            f"{confidence:.0%}",
            (x - 20, y + 5),
            self.font,
            0.6,
            self.theme.text_primary,
            2
        )
        
        # Label
        cv2.putText(
            output,
            label,
            (x - radius, y + radius + 20),
            self.font,
            0.4,
            self.theme.text_secondary,
            1
        )
        
        return output


class UIRenderer:
    """
    Renderizador principal de interface.
    
    Coordena todos os elementos visuais:
    - HUD com métricas
    - Overlays de análise
    - Bounding boxes
    - Painel de resultados
    """
    
    def __init__(self, theme: UITheme = UITheme.MEDICAL):
        """
        Args:
            theme: Tema de cores
        """
        self.theme = THEMES.get(theme, THEMES[UITheme.DARK])
        self.hud = HUDPanel(position="top-right", theme=theme)
        self.overlay = AnalysisOverlay(theme=theme)
        
        # Estado
        self._fps_history: List[float] = []
        self._last_time = time.time()
        
    def update_fps(self) -> float:
        """Atualiza e retorna FPS atual"""
        current_time = time.time()
        fps = 1.0 / max(current_time - self._last_time, 0.001)
        self._last_time = current_time
        
        self._fps_history.append(fps)
        if len(self._fps_history) > 30:
            self._fps_history.pop(0)
            
        return np.mean(self._fps_history)
        
    def render_realtime_view(
        self,
        frame: np.ndarray,
        detections: List[Dict],
        fps: Optional[float] = None,
        mode: str = "detection",
        extra_info: Optional[Dict] = None
    ) -> np.ndarray:
        """
        Renderiza view de tempo real com todos os elementos.
        
        Args:
            frame: Frame de vídeo
            detections: Lista de detecções
            fps: FPS atual (calculado se não fornecido)
            mode: Modo de operação
            extra_info: Informações extras para HUD
            
        Returns:
            Frame renderizado
        """
        output = frame.copy()
        
        if fps is None:
            fps = self.update_fps()
            
        # Desenha detecções
        for det in detections:
            bbox = det.get("bbox", (0, 0, 100, 100))
            confidence = det.get("confidence", 0.0)
            wound_type = det.get("type", "wound")
            label = det.get("label", "Ferida")
            
            output = self.overlay.draw_detection_box(
                output,
                bbox=bbox,
                label=label,
                confidence=confidence,
                wound_type=wound_type
            )
            
        # Atualiza HUD
        self.hud.clear()
        self.hud.set_title("REDISUS", f"Modo: {mode}")
        
        # FPS
        fps_color = self.theme.success if fps >= 25 else (
            self.theme.warning if fps >= 15 else self.theme.danger
        )
        self.hud.add_element("FPS", f"{fps:.1f}", color=fps_color)
        
        # Detecções
        self.hud.add_element("Detecções", len(detections))
        
        # Info extra
        if extra_info:
            for key, value in extra_info.items():
                self.hud.add_element(key, value)
                
        # Renderiza HUD
        output = self.hud.render(output)
        
        # Instruções no rodapé
        output = self._draw_instructions(output, mode)
        
        return output
        
    def render_analysis_view(
        self,
        frame: np.ndarray,
        analysis_result: Dict,
        show_tissue_map: bool = True
    ) -> np.ndarray:
        """
        Renderiza view de análise completa.
        
        Args:
            frame: Frame original ou com máscara
            analysis_result: Resultado da análise
            show_tissue_map: Se deve mostrar mapa de tecidos
            
        Returns:
            Frame com visualização de análise
        """
        output = frame.copy()
        h, w = output.shape[:2]
        
        # Detecção principal
        if "bbox" in analysis_result:
            output = self.overlay.draw_detection_box(
                output,
                bbox=analysis_result["bbox"],
                label=analysis_result.get("etiology", "Ferida"),
                confidence=analysis_result.get("confidence", 0),
                wound_type=analysis_result.get("etiology_type", "wound")
            )
            
        # Distribuição de tecidos
        if show_tissue_map and "tissue_percentages" in analysis_result:
            output = self.overlay.draw_tissue_distribution(
                output,
                tissue_percentages=analysis_result["tissue_percentages"],
                position=(20, h - 200)
            )
            
        # Medidor de confiança
        if "confidence" in analysis_result:
            output = self.overlay.draw_confidence_meter(
                output,
                confidence=analysis_result["confidence"],
                position=(w - 70, h - 80),
                label="Confiança"
            )
            
        # Painel de resultado
        output = self._draw_result_panel(output, analysis_result)
        
        return output
        
    def _draw_instructions(self, frame: np.ndarray, mode: str) -> np.ndarray:
        """Desenha instruções na parte inferior"""
        output = frame.copy()
        h, w = output.shape[:2]
        
        instructions = {
            "detection": "[SPACE] Capturar | [A] Auto | [S] Salvar | [Q] Sair",
            "analysis": "[ENTER] Confirmar | [R] Recapturar | [Q] Voltar",
            "review": "[←/→] Navegar | [ENTER] Selecionar | [Q] Fechar"
        }
        
        text = instructions.get(mode, "[Q] Sair")
        
        # Background
        overlay = output.copy()
        cv2.rectangle(overlay, (0, h - 35), (w, h), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.7, output, 0.3, 0, output)
        
        # Texto
        cv2.putText(
            output,
            text,
            (20, h - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (200, 200, 200),
            1
        )
        
        # Timestamp
        timestamp = time.strftime("%H:%M:%S")
        cv2.putText(
            output,
            timestamp,
            (w - 80, h - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (150, 150, 150),
            1
        )
        
        return output
        
    def _draw_result_panel(self, frame: np.ndarray, result: Dict) -> np.ndarray:
        """Desenha painel de resultado lateral"""
        output = frame.copy()
        h, w = output.shape[:2]
        
        panel_width = 300
        x = w - panel_width - 15
        y = 15
        
        # Background do painel
        overlay = output.copy()
        cv2.rectangle(
            overlay,
            (x, y),
            (w - 15, y + 250),
            self.theme.panel_bg,
            -1
        )
        cv2.rectangle(
            overlay,
            (x, y),
            (w - 15, y + 250),
            self.theme.accent,
            2
        )
        cv2.addWeighted(overlay, 0.9, output, 0.1, 0, output)
        
        # Título
        cv2.putText(
            output,
            "RESULTADO DA ANÁLISE",
            (x + 15, y + 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            self.theme.accent,
            2
        )
        
        # Etiologia
        etiology = result.get("etiology", "Não identificado")
        cv2.putText(
            output,
            "Etiologia:",
            (x + 15, y + 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            self.theme.text_muted,
            1
        )
        cv2.putText(
            output,
            etiology,
            (x + 15, y + 85),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            self.theme.text_primary,
            1
        )
        
        # Descrição
        description = result.get("description", "")
        if description:
            # Quebra texto longo
            words = description.split()
            lines = []
            current_line = ""
            for word in words:
                if len(current_line + word) < 35:
                    current_line += word + " "
                else:
                    lines.append(current_line.strip())
                    current_line = word + " "
            if current_line:
                lines.append(current_line.strip())
                
            for i, line in enumerate(lines[:3]):  # Máximo 3 linhas
                cv2.putText(
                    output,
                    line,
                    (x + 15, y + 110 + i * 18),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    self.theme.text_secondary,
                    1
                )
                
        # Recomendação
        if result.get("needs_review", False):
            cv2.putText(
                output,
                "⚠ Revisão recomendada",
                (x + 15, y + 200),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                self.theme.warning,
                1
            )
            
        return output
