"""
REDISUS - Sistema de Diagnóstico de Feridas
Módulo de Segmentação de Tecidos (U-Net)

Este módulo implementa a segmentação semântica pixel-a-pixel para
identificar tipos de tecido em feridas:
- Granulação (vermelho)
- Esfacelo (amarelo/branco)
- Necrose (preto)
- Pele Perilesional (verde)
"""
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger

from ..core.config import (
    ModelConfig,
    TissueType,
    TISSUE_NAMES,
    get_tissue_color_map,
)
from ..core.exceptions import InferenceError, ModelLoadError


@dataclass
class TissueSegmentationResult:
    """Resultado da segmentação de tecidos"""
    mask: np.ndarray  # Shape: (H, W), valores 0-4 (classes)
    probabilities: np.ndarray  # Shape: (H, W, num_classes)
    tissue_percentages: Dict[str, float]  # Porcentagem de cada tecido
    wound_area_pixels: int  # Área total da ferida em pixels
    original_size: Tuple[int, int]  # (width, height) original
    inference_time_ms: float
    
    def get_tissue_mask(self, tissue_type: TissueType) -> np.ndarray:
        """Retorna máscara binária para um tipo de tecido específico"""
        return (self.mask == tissue_type.value).astype(np.uint8)
    
    def get_colored_mask(self) -> np.ndarray:
        """Retorna máscara colorida para visualização"""
        color_map = get_tissue_color_map()
        colored = color_map[self.mask]
        return colored
    
    def get_overlay(
        self,
        original_image: np.ndarray,
        alpha: float = 0.5
    ) -> np.ndarray:
        """Retorna imagem original com overlay da segmentação"""
        colored_mask = self.get_colored_mask()
        
        # Resize mask para tamanho original se necessário
        if colored_mask.shape[:2] != original_image.shape[:2]:
            colored_mask = cv2.resize(
                colored_mask,
                (original_image.shape[1], original_image.shape[0]),
                interpolation=cv2.INTER_NEAREST
            )
        
        # Converte BGR se necessário
        if len(original_image.shape) == 3 and original_image.shape[2] == 3:
            colored_mask_bgr = cv2.cvtColor(colored_mask, cv2.COLOR_RGB2BGR)
        else:
            colored_mask_bgr = colored_mask
        
        # Blend
        overlay = cv2.addWeighted(original_image, 1 - alpha, colored_mask_bgr, alpha, 0)
        
        return overlay


class UNetSegmenter:
    """
    Segmentador baseado em U-Net para análise de tecidos de feridas.
    
    Arquitetura:
    - Encoder: EfficientNet-B0 (pré-treinado ImageNet)
    - Decoder: U-Net padrão com skip connections
    - Output: 5 classes (background + 4 tipos de tecido)
    
    Input: 512x512 RGB
    Output: 512x512 máscara de segmentação
    """
    
    NUM_CLASSES = 5
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        config: Optional[ModelConfig] = None
    ):
        """
        Args:
            model_path: Caminho para o modelo (.onnx ou .pt)
            config: Configurações do modelo
        """
        self.config = config or ModelConfig(
            model_path=model_path or "models/unet_tissue_segmentation.onnx",
            input_size=(512, 512),
            num_classes=5,
            confidence_threshold=0.5,
            device="cuda"
        )
        
        self._session = None  # ONNX Runtime
        self._model = None    # PyTorch model
        self._device = None
        
    def load_model(self, model_path: Optional[str] = None):
        """Carrega o modelo de segmentação"""
        path = Path(model_path or self.config.model_path)
        
        if not path.exists():
            logger.warning(
                f"Modelo não encontrado: {path}. "
                "Usando modo de simulação."
            )
            self._model = "simulation"
            return
        
        suffix = path.suffix.lower()
        
        try:
            if suffix == ".onnx":
                self._load_onnx(str(path))
            elif suffix == ".pt":
                self._load_pytorch(str(path))
            else:
                raise ModelLoadError(f"Formato não suportado: {suffix}")
            
            logger.info(f"Modelo de segmentação carregado: {path.name}")
            
        except Exception as e:
            raise ModelLoadError(f"Erro ao carregar modelo: {e}")
    
    def _load_onnx(self, model_path: str):
        """Carrega modelo ONNX"""
        try:
            import onnxruntime as ort
            
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            self._session = ort.InferenceSession(model_path, providers=providers)
            
        except ImportError:
            raise ModelLoadError("onnxruntime não instalado")
    
    def _load_pytorch(self, model_path: str):
        """Carrega modelo PyTorch"""
        try:
            import torch
            
            self._device = torch.device(
                "cuda" if torch.cuda.is_available() and self.config.device == "cuda"
                else "cpu"
            )
            
            self._model = torch.load(model_path, map_location=self._device)
            self._model.eval()
            
        except ImportError:
            raise ModelLoadError("torch não instalado")
    
    def segment(self, image: np.ndarray) -> TissueSegmentationResult:
        """
        Realiza segmentação de tecidos em uma imagem.
        
        Args:
            image: Imagem BGR (numpy array)
            
        Returns:
            TissueSegmentationResult com máscara e análises
        """
        start_time = time.perf_counter()
        
        original_size = (image.shape[1], image.shape[0])
        
        # Pré-processamento
        input_tensor = self._preprocess(image)
        
        # Inferência
        if self._model == "simulation":
            mask, probs = self._simulate_segmentation(image)
        elif self._session is not None:
            mask, probs = self._infer_onnx(input_tensor)
        elif self._model is not None:
            mask, probs = self._infer_pytorch(input_tensor)
        else:
            raise InferenceError("Modelo não carregado")
        
        # Resize para tamanho original
        mask_resized = cv2.resize(
            mask,
            original_size,
            interpolation=cv2.INTER_NEAREST
        )
        
        # Calcula porcentagens
        tissue_percentages = self._calculate_percentages(mask_resized)
        
        # Área da ferida (exclui background e pele perilesional)
        wound_mask = (mask_resized != TissueType.BACKGROUND.value) & \
                     (mask_resized != TissueType.PERIWOUND.value)
        wound_area = np.sum(wound_mask)
        
        inference_time = (time.perf_counter() - start_time) * 1000
        
        return TissueSegmentationResult(
            mask=mask_resized,
            probabilities=probs,
            tissue_percentages=tissue_percentages,
            wound_area_pixels=wound_area,
            original_size=original_size,
            inference_time_ms=inference_time
        )
    
    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """Pré-processa imagem para inferência"""
        input_h, input_w = self.config.input_size
        
        # Resize
        resized = cv2.resize(image, (input_w, input_h))
        
        # BGR -> RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # Normaliza (ImageNet stats)
        normalized = rgb.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        normalized = (normalized - mean) / std
        
        # (H, W, C) -> (1, C, H, W)
        tensor = np.transpose(normalized, (2, 0, 1))
        tensor = np.expand_dims(tensor, axis=0).astype(np.float32)
        
        return tensor
    
    def _infer_onnx(self, input_tensor: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Inferência ONNX"""
        input_name = self._session.get_inputs()[0].name
        output_name = self._session.get_outputs()[0].name
        
        output = self._session.run([output_name], {input_name: input_tensor})[0]
        
        # Output shape: (1, num_classes, H, W)
        probs = self._softmax(output[0])  # (num_classes, H, W)
        probs = np.transpose(probs, (1, 2, 0))  # (H, W, num_classes)
        mask = np.argmax(probs, axis=2)
        
        return mask.astype(np.uint8), probs
    
    def _infer_pytorch(self, input_tensor: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Inferência PyTorch"""
        import torch
        
        with torch.no_grad():
            tensor = torch.from_numpy(input_tensor).to(self._device)
            output = self._model(tensor)
            
            probs = torch.softmax(output, dim=1)
            probs = probs[0].cpu().numpy()  # (num_classes, H, W)
            probs = np.transpose(probs, (1, 2, 0))  # (H, W, num_classes)
            
            mask = np.argmax(probs, axis=2)
        
        return mask.astype(np.uint8), probs
    
    def _simulate_segmentation(
        self,
        image: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Simula segmentação baseada em cores para demonstração.
        
        Na produção, substitua pelo modelo U-Net treinado.
        """
        h, w = self.config.input_size
        resized = cv2.resize(image, (w, h))
        
        # Converte para HSV para análise de cor
        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        
        # Inicializa máscara como background
        mask = np.zeros((h, w), dtype=np.uint8)
        probs = np.zeros((h, w, self.NUM_CLASSES), dtype=np.float32)
        probs[:, :, 0] = 0.5  # Background default
        
        # Detecta região de interesse (área não-pele)
        # Tons de pele em HSV
        lower_skin = np.array([0, 20, 70])
        upper_skin = np.array([20, 150, 255])
        skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
        
        # Granulação (vermelho intenso)
        lower_red = np.array([0, 100, 100])
        upper_red = np.array([10, 255, 255])
        granulation_mask = cv2.inRange(hsv, lower_red, upper_red)
        
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([180, 255, 255])
        granulation_mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        granulation_mask = cv2.bitwise_or(granulation_mask, granulation_mask2)
        
        # Esfacelo (amarelo/branco)
        lower_yellow = np.array([15, 50, 150])
        upper_yellow = np.array([35, 255, 255])
        slough_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
        
        # Branco (também esfacelo)
        lower_white = np.array([0, 0, 200])
        upper_white = np.array([180, 30, 255])
        white_mask = cv2.inRange(hsv, lower_white, upper_white)
        slough_mask = cv2.bitwise_or(slough_mask, white_mask)
        
        # Necrose (preto/marrom escuro)
        lower_dark = np.array([0, 0, 0])
        upper_dark = np.array([180, 255, 50])
        necrosis_mask = cv2.inRange(hsv, lower_dark, upper_dark)
        
        # Aplica máscaras (prioridade: necrose > esfacelo > granulação > perilesional)
        mask[skin_mask > 0] = TissueType.PERIWOUND.value
        mask[granulation_mask > 0] = TissueType.GRANULATION.value
        mask[slough_mask > 0] = TissueType.SLOUGH.value
        mask[necrosis_mask > 0] = TissueType.NECROSIS.value
        
        # Suaviza com operações morfológicas
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # Gera probabilidades simuladas
        for i in range(self.NUM_CLASSES):
            class_mask = (mask == i).astype(np.float32)
            probs[:, :, i] = class_mask * 0.8 + 0.05  # 80% conf onde detectado
        
        # Normaliza
        probs = probs / probs.sum(axis=2, keepdims=True)
        
        return mask, probs
    
    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        """Softmax ao longo do eixo 0 (classes)"""
        exp_x = np.exp(x - np.max(x, axis=0, keepdims=True))
        return exp_x / np.sum(exp_x, axis=0, keepdims=True)
    
    @staticmethod
    def _calculate_percentages(mask: np.ndarray) -> Dict[str, float]:
        """Calcula porcentagem de cada tipo de tecido"""
        total_pixels = mask.size
        percentages = {}
        
        for tissue_type in TissueType:
            count = np.sum(mask == tissue_type.value)
            percentage = (count / total_pixels) * 100
            percentages[TISSUE_NAMES[tissue_type.value]] = round(percentage, 2)
        
        return percentages


class WoundAreaCalculator:
    """
    Calculadora de área de feridas.
    
    Métodos:
    - Cálculo por pixels
    - Estimativa em cm² usando referência de escala
    - Tracking de evolução temporal
    """
    
    # Diâmetro padrão de referência (ex: moeda, régua) em cm
    DEFAULT_REFERENCE_SIZE_CM = 2.5
    
    @staticmethod
    def calculate_area_pixels(mask: np.ndarray) -> int:
        """Calcula área da ferida em pixels"""
        wound_mask = (mask != TissueType.BACKGROUND.value) & \
                     (mask != TissueType.PERIWOUND.value)
        return int(np.sum(wound_mask))
    
    @staticmethod
    def calculate_area_cm2(
        mask: np.ndarray,
        pixels_per_cm: float
    ) -> float:
        """
        Calcula área da ferida em cm².
        
        Args:
            mask: Máscara de segmentação
            pixels_per_cm: Escala de pixels por centímetro
            
        Returns:
            Área em cm²
        """
        area_pixels = WoundAreaCalculator.calculate_area_pixels(mask)
        pixels_per_cm2 = pixels_per_cm ** 2
        return area_pixels / pixels_per_cm2
    
    @staticmethod
    def calculate_reduction(
        area_current: float,
        area_previous: float
    ) -> Dict[str, float]:
        """
        Calcula redução de área entre duas medições.
        
        Returns:
            Dict com redução absoluta e percentual
        """
        if area_previous <= 0:
            return {"absolute": 0.0, "percentage": 0.0}
        
        absolute = area_previous - area_current
        percentage = (absolute / area_previous) * 100
        
        return {
            "absolute": round(absolute, 2),
            "percentage": round(percentage, 2)
        }
    
    @staticmethod
    def estimate_scale_from_reference(
        image: np.ndarray,
        reference_bbox: Tuple[int, int, int, int],
        reference_size_cm: float = DEFAULT_REFERENCE_SIZE_CM
    ) -> float:
        """
        Estima escala pixels/cm usando objeto de referência.
        
        Args:
            image: Imagem original
            reference_bbox: Bounding box do objeto de referência (x1, y1, x2, y2)
            reference_size_cm: Tamanho conhecido do objeto em cm
            
        Returns:
            Pixels por centímetro
        """
        x1, y1, x2, y2 = reference_bbox
        reference_pixels = max(x2 - x1, y2 - y1)  # Usa maior dimensão
        
        pixels_per_cm = reference_pixels / reference_size_cm
        return pixels_per_cm
