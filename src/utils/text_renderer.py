"""
REDISUS - Renderizador de Texto Seguro
Solucao para problemas de encoding UTF-8 no OpenCV cv2.putText

O OpenCV tem problemas com caracteres especiais (acentos, cedilha, etc.)
Este modulo fornece funcoes de renderizacao de texto usando apenas ASCII
ou alternativas com PIL para suporte completo a Unicode.
"""
import cv2
import numpy as np
from typing import Tuple, Optional
from pathlib import Path

# Tenta importar PIL para renderizacao Unicode
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# Mapa de traducao de caracteres especiais para ASCII
CHAR_MAP = {
    # Acentos
    'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a', 'ä': 'a',
    'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
    'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
    'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o', 'ö': 'o',
    'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
    'ç': 'c',
    'ñ': 'n',
    # Maiusculas
    'Á': 'A', 'À': 'A', 'Ã': 'A', 'Â': 'A', 'Ä': 'A',
    'É': 'E', 'È': 'E', 'Ê': 'E', 'Ë': 'E',
    'Í': 'I', 'Ì': 'I', 'Î': 'I', 'Ï': 'I',
    'Ó': 'O', 'Ò': 'O', 'Õ': 'O', 'Ô': 'O', 'Ö': 'O',
    'Ú': 'U', 'Ù': 'U', 'Û': 'U', 'Ü': 'U',
    'Ç': 'C',
    'Ñ': 'N',
}

# Traducoes de termos medicos
MEDICAL_TRANSLATIONS = {
    # Etiologias
    'Úlcera Venosa': 'Ulcera Venosa',
    'Úlcera Arterial': 'Ulcera Arterial',
    'Pé Diabético': 'Pe Diabetico',
    'Lesão por Pressão': 'Lesao por Pressao',
    'Ferida Cirúrgica': 'Ferida Cirurgica',
    'Traumática': 'Traumatica',
    'Queimadura': 'Queimadura',
    
    # Tecidos
    'Granulação': 'Granulacao',
    'Necrótica': 'Necrotica',
    'Epitelização': 'Epitelizacao',
    'Esfacelo': 'Esfacelo',
    'Fibrina': 'Fibrina',
    
    # Status
    'Análise': 'Analise',
    'Detecção': 'Deteccao',
    'Confiança': 'Confianca',
    'Saúde': 'Saude',
    'Descrição': 'Descricao',
    'Composição': 'Composicao',
    
    # Outros
    'Atenção': 'Atencao',
    'Revisão': 'Revisao',
    'Recomendação': 'Recomendacao',
}


def to_ascii(text: str) -> str:
    """
    Converte texto para ASCII puro, substituindo caracteres especiais.
    
    Args:
        text: Texto com possiveis caracteres especiais
        
    Returns:
        Texto ASCII puro
    """
    # Primeiro tenta traducoes conhecidas
    for original, replacement in MEDICAL_TRANSLATIONS.items():
        text = text.replace(original, replacement)
    
    # Depois substitui caracteres individuais
    result = []
    for char in text:
        if char in CHAR_MAP:
            result.append(CHAR_MAP[char])
        elif ord(char) < 128:
            result.append(char)
        else:
            # Caractere desconhecido - substitui por ?
            result.append('?')
    
    return ''.join(result)


def put_text_safe(
    image: np.ndarray,
    text: str,
    position: Tuple[int, int],
    font_scale: float = 0.5,
    color: Tuple[int, int, int] = (255, 255, 255),
    thickness: int = 1,
    font: int = cv2.FONT_HERSHEY_SIMPLEX,
    background: Optional[Tuple[int, int, int]] = None,
    padding: int = 2
) -> np.ndarray:
    """
    Renderiza texto de forma segura, convertendo para ASCII.
    
    Args:
        image: Imagem BGR
        text: Texto a renderizar
        position: Posicao (x, y)
        font_scale: Escala da fonte
        color: Cor BGR do texto
        thickness: Espessura
        font: Tipo de fonte OpenCV
        background: Cor de fundo (opcional)
        padding: Padding do fundo
        
    Returns:
        Imagem com texto
    """
    # Converte para ASCII
    safe_text = to_ascii(text)
    
    # Calcula tamanho do texto
    (text_w, text_h), baseline = cv2.getTextSize(safe_text, font, font_scale, thickness)
    
    x, y = position
    
    # Desenha fundo se especificado
    if background is not None:
        cv2.rectangle(
            image,
            (x - padding, y - text_h - padding),
            (x + text_w + padding, y + baseline + padding),
            background,
            -1
        )
    
    # Desenha texto
    cv2.putText(image, safe_text, (x, y), font, font_scale, color, thickness, cv2.LINE_AA)
    
    return image


def put_text_unicode(
    image: np.ndarray,
    text: str,
    position: Tuple[int, int],
    font_size: int = 16,
    color: Tuple[int, int, int] = (255, 255, 255),
    font_path: Optional[str] = None
) -> np.ndarray:
    """
    Renderiza texto com suporte completo a Unicode usando PIL.
    
    Requer PIL instalado.
    
    Args:
        image: Imagem BGR
        text: Texto a renderizar (pode ter caracteres especiais)
        position: Posicao (x, y)
        font_size: Tamanho da fonte em pixels
        color: Cor BGR do texto
        font_path: Caminho para arquivo de fonte .ttf (opcional)
        
    Returns:
        Imagem com texto
    """
    if not HAS_PIL:
        # Fallback para ASCII
        return put_text_safe(image, text, position, font_scale=font_size/30, color=color)
    
    # Converte BGR para RGB
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(image_rgb)
    draw = ImageDraw.Draw(pil_image)
    
    # Carrega fonte
    if font_path and Path(font_path).exists():
        font = ImageFont.truetype(font_path, font_size)
    else:
        try:
            # Tenta fontes do sistema
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except:
                font = ImageFont.load_default()
    
    # Converte cor BGR para RGB
    color_rgb = (color[2], color[1], color[0])
    
    # Desenha texto
    draw.text(position, text, font=font, fill=color_rgb)
    
    # Converte de volta para BGR
    result = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    
    return result


class SafeTextRenderer:
    """
    Renderizador de texto seguro para OpenCV.
    
    Gerencia cache de traducoes e fornece interface unificada
    para renderizacao de texto ASCII ou Unicode.
    """
    
    def __init__(self, use_unicode: bool = False, font_path: Optional[str] = None):
        """
        Args:
            use_unicode: Se True e PIL disponivel, usa renderizacao Unicode
            font_path: Caminho para fonte .ttf (para Unicode)
        """
        self.use_unicode = use_unicode and HAS_PIL
        self.font_path = font_path
        
        # Cache de traducoes
        self._cache = {}
        
    def translate(self, text: str) -> str:
        """Traduz texto para ASCII se necessario"""
        if text in self._cache:
            return self._cache[text]
            
        translated = to_ascii(text)
        self._cache[text] = translated
        return translated
    
    def put_text(
        self,
        image: np.ndarray,
        text: str,
        position: Tuple[int, int],
        font_scale: float = 0.5,
        color: Tuple[int, int, int] = (255, 255, 255),
        thickness: int = 1,
        background: Optional[Tuple[int, int, int]] = None
    ) -> np.ndarray:
        """
        Renderiza texto na imagem.
        
        Args:
            image: Imagem BGR
            text: Texto a renderizar
            position: Posicao (x, y)
            font_scale: Escala da fonte (para ASCII)
            color: Cor BGR
            thickness: Espessura (para ASCII)
            background: Cor de fundo opcional
            
        Returns:
            Imagem com texto
        """
        if self.use_unicode:
            return put_text_unicode(
                image, text, position,
                font_size=int(font_scale * 30),
                color=color,
                font_path=self.font_path
            )
        else:
            return put_text_safe(
                image, text, position,
                font_scale=font_scale,
                color=color,
                thickness=thickness,
                background=background
            )
    
    def put_multiline(
        self,
        image: np.ndarray,
        text: str,
        position: Tuple[int, int],
        font_scale: float = 0.5,
        color: Tuple[int, int, int] = (255, 255, 255),
        thickness: int = 1,
        line_spacing: int = 5
    ) -> np.ndarray:
        """
        Renderiza texto multilinhas.
        
        Args:
            image: Imagem BGR
            text: Texto com \n para quebras de linha
            position: Posicao inicial (x, y)
            font_scale: Escala da fonte
            color: Cor BGR
            thickness: Espessura
            line_spacing: Espacamento entre linhas
            
        Returns:
            Imagem com texto
        """
        lines = text.split('\n')
        x, y = position
        
        for line in lines:
            image = self.put_text(image, line, (x, y), font_scale, color, thickness)
            
            # Calcula altura da linha
            if self.use_unicode:
                line_height = int(font_scale * 30) + line_spacing
            else:
                (_, text_h), _ = cv2.getTextSize(
                    self.translate(line) or "Ag",
                    cv2.FONT_HERSHEY_SIMPLEX,
                    font_scale,
                    thickness
                )
                line_height = text_h + line_spacing
                
            y += line_height
            
        return image


# Instancia global para uso conveniente
_renderer = SafeTextRenderer(use_unicode=False)


def safe_putText(
    image: np.ndarray,
    text: str,
    position: Tuple[int, int],
    font_scale: float = 0.5,
    color: Tuple[int, int, int] = (255, 255, 255),
    thickness: int = 1
) -> np.ndarray:
    """
    Funcao de conveniencia para renderizar texto seguro.
    
    Substitui cv2.putText com suporte a caracteres especiais.
    """
    return _renderer.put_text(image, text, position, font_scale, color, thickness)
