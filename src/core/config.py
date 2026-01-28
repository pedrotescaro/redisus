"""
REDISUS - Sistema de Diagnóstico de Feridas
Módulo de Configuração Global
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


class TissueType(Enum):
    """Tipos de tecido para segmentação"""
    BACKGROUND = 0
    GRANULATION = 1  # Granulação (vermelho)
    SLOUGH = 2       # Esfacelo (amarelo/branco)
    NECROSIS = 3     # Necrose (preto)
    PERIWOUND = 4    # Pele perilesional


class EtiologyType(Enum):
    """Tipos de etiologia para classificação"""
    VENOUS_ULCER = 0      # Úlcera venosa
    ARTERIAL_ULCER = 1    # Úlcera arterial
    DIABETIC_FOOT = 2     # Pé diabético (neuropática)
    PRESSURE_INJURY = 3   # Lesão por pressão
    SURGICAL_WOUND = 4    # Ferida cirúrgica


@dataclass
class TissueColors:
    """Cores RGB para visualização de tecidos"""
    BACKGROUND: Tuple[int, int, int] = (128, 128, 128)
    GRANULATION: Tuple[int, int, int] = (255, 0, 0)      # Vermelho
    SLOUGH: Tuple[int, int, int] = (255, 255, 0)         # Amarelo
    NECROSIS: Tuple[int, int, int] = (0, 0, 0)           # Preto
    PERIWOUND: Tuple[int, int, int] = (0, 255, 0)        # Verde


@dataclass
class ModelConfig:
    """Configuração de um modelo de inferência"""
    model_path: str
    input_size: Tuple[int, int]
    num_classes: int
    confidence_threshold: float = 0.5
    device: str = "cuda"  # "cuda", "cpu", "tflite"


@dataclass
class CameraConfig:
    """Configuração da câmera/webcam"""
    camera_id: int = 0
    width: int = 1920
    height: int = 1080
    fps: int = 30
    buffer_size: int = 1
    auto_focus: bool = True


@dataclass
class RealtimeConfig:
    """Configuração para processamento em tempo real"""
    # Modelo de detecção
    detector: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_path="models/yolo_wound_nano.onnx",
        input_size=(320, 320),
        num_classes=1,
        confidence_threshold=0.5,
        device="cuda"
    ))
    
    # Performance
    target_fps: int = 30
    skip_frames: int = 0  # 0 = processar todos
    async_inference: bool = True
    
    # Visualização
    draw_confidence: bool = True
    box_color: Tuple[int, int, int] = (0, 255, 0)
    box_thickness: int = 2


@dataclass
class DiagnosisConfig:
    """Configuração para diagnóstico profundo"""
    # Modelo de segmentação
    segmenter: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_path="models/unet_tissue_segmentation.onnx",
        input_size=(512, 512),
        num_classes=5,
        confidence_threshold=0.5,
        device="cuda"
    ))
    
    # Modelo de classificação
    classifier: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_path="models/efficientnet_etiology.onnx",
        input_size=(224, 224),
        num_classes=5,
        confidence_threshold=0.7,
        device="cuda"
    ))
    
    # Opções
    parallel_processing: bool = True
    save_intermediate: bool = False


@dataclass 
class AppConfig:
    """Configuração principal da aplicação"""
    # Diretórios
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)
    models_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent / "models")
    data_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent / "data")
    output_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent / "output")
    
    # Módulos
    camera: CameraConfig = field(default_factory=CameraConfig)
    realtime: RealtimeConfig = field(default_factory=RealtimeConfig)
    diagnosis: DiagnosisConfig = field(default_factory=DiagnosisConfig)
    
    # Cores dos tecidos
    tissue_colors: TissueColors = field(default_factory=TissueColors)
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    def __post_init__(self):
        """Cria diretórios necessários"""
        self.output_dir.mkdir(parents=True, exist_ok=True)


# Instância global de configuração
config = AppConfig()


# Mapeamentos úteis
TISSUE_NAMES: Dict[int, str] = {
    0: "Background",
    1: "Granulação",
    2: "Esfacelo",
    3: "Necrose",
    4: "Pele Perilesional"
}

ETIOLOGY_NAMES: Dict[int, str] = {
    0: "Úlcera Venosa",
    1: "Úlcera Arterial",
    2: "Pé Diabético",
    3: "Lesão por Pressão",
    4: "Ferida Cirúrgica"
}

ETIOLOGY_DESCRIPTIONS: Dict[int, str] = {
    0: "Úlcera causada por insuficiência venosa crônica, geralmente localizada no terço inferior da perna.",
    1: "Úlcera causada por doença arterial periférica, com comprometimento do fluxo sanguíneo.",
    2: "Úlcera neuropática, comum em pacientes diabéticos, geralmente na região plantar.",
    3: "Lesão causada por pressão prolongada em proeminências ósseas.",
    4: "Ferida resultante de procedimento cirúrgico, em processo de cicatrização."
}


def get_tissue_color_map() -> np.ndarray:
    """
    Retorna array de cores para visualização de máscara de segmentação.
    Shape: (num_classes, 3) - RGB
    """
    colors = TissueColors()
    return np.array([
        colors.BACKGROUND,
        colors.GRANULATION,
        colors.SLOUGH,
        colors.NECROSIS,
        colors.PERIWOUND
    ], dtype=np.uint8)
