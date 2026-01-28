"""
REDISUS - Sistema de Diagnóstico de Feridas
Módulo de Classificação de Etiologia

Este módulo classifica a causa base da ferida analisando padrões
visuais, localização e formato:
- Úlcera Venosa
- Úlcera Arterial  
- Úlcera Neuropática (Pé Diabético)
- Lesão por Pressão
- Ferida Cirúrgica
"""
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger

from ..core.config import (
    EtiologyType,
    ModelConfig,
    ETIOLOGY_NAMES,
    ETIOLOGY_DESCRIPTIONS,
)
from ..core.exceptions import InferenceError, ModelLoadError


@dataclass
class EtiologyPrediction:
    """Resultado da classificação de etiologia"""
    class_id: int
    class_name: str
    confidence: float
    description: str
    
    @property
    def etiology_type(self) -> EtiologyType:
        return EtiologyType(self.class_id)


@dataclass
class EtiologyClassificationResult:
    """Resultado completo da classificação"""
    primary_prediction: EtiologyPrediction
    all_predictions: List[EtiologyPrediction]  # Top-K ordenado por confidence
    probabilities: Dict[str, float]  # Todas as classes
    features: Optional[Dict[str, float]]  # Features extraídas (opcional)
    inference_time_ms: float
    
    @property
    def is_confident(self) -> bool:
        """Retorna True se a predição primária tem alta confiança"""
        return self.primary_prediction.confidence >= 0.7
    
    @property
    def needs_review(self) -> bool:
        """Retorna True se a classificação deve ser revisada por especialista"""
        # Se a diferença entre top-2 é pequena, pode ser ambíguo
        if len(self.all_predictions) >= 2:
            diff = self.all_predictions[0].confidence - self.all_predictions[1].confidence
            return diff < 0.15 or self.primary_prediction.confidence < 0.6
        return self.primary_prediction.confidence < 0.6


class EtiologyClassifier:
    """
    Classificador de etiologia baseado em CNN (EfficientNet).
    
    Arquitetura:
    - Backbone: EfficientNet-B3 (pré-treinado ImageNet)
    - Head: Global Average Pooling + Dense layers
    - Output: 5 classes com Softmax
    
    Features analisadas pelo modelo:
    - Padrões de cor e textura
    - Forma e bordas da ferida
    - Localização inferida (quando disponível)
    - Características morfológicas
    """
    
    NUM_CLASSES = 5
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        config: Optional[ModelConfig] = None
    ):
        """
        Args:
            model_path: Caminho para o modelo
            config: Configurações
        """
        self.config = config or ModelConfig(
            model_path=model_path or "models/efficientnet_etiology.onnx",
            input_size=(224, 224),
            num_classes=5,
            confidence_threshold=0.7,
            device="cuda"
        )
        
        self._session = None
        self._model = None
        self._device = None
        
    def load_model(self, model_path: Optional[str] = None):
        """Carrega o modelo de classificação"""
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
            
            logger.info(f"Modelo de classificação carregado: {path.name}")
            
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
    
    def classify(
        self,
        image: np.ndarray,
        top_k: int = 3
    ) -> EtiologyClassificationResult:
        """
        Classifica a etiologia de uma ferida.
        
        Args:
            image: Imagem BGR da ferida
            top_k: Número de top predições a retornar
            
        Returns:
            EtiologyClassificationResult
        """
        start_time = time.perf_counter()
        
        # Pré-processamento
        input_tensor = self._preprocess(image)
        
        # Inferência
        if self._model == "simulation":
            probs, features = self._simulate_classification(image)
        elif self._session is not None:
            probs, features = self._infer_onnx(input_tensor)
        elif self._model is not None:
            probs, features = self._infer_pytorch(input_tensor)
        else:
            raise InferenceError("Modelo não carregado")
        
        # Processa resultados
        all_predictions = self._create_predictions(probs)
        all_predictions.sort(key=lambda p: p.confidence, reverse=True)
        
        top_predictions = all_predictions[:top_k]
        primary = top_predictions[0]
        
        probabilities = {
            ETIOLOGY_NAMES[i]: round(float(probs[i]), 4)
            for i in range(self.NUM_CLASSES)
        }
        
        inference_time = (time.perf_counter() - start_time) * 1000
        
        return EtiologyClassificationResult(
            primary_prediction=primary,
            all_predictions=top_predictions,
            probabilities=probabilities,
            features=features,
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
    
    def _infer_onnx(
        self,
        input_tensor: np.ndarray
    ) -> Tuple[np.ndarray, Optional[Dict]]:
        """Inferência ONNX"""
        input_name = self._session.get_inputs()[0].name
        outputs = self._session.run(None, {input_name: input_tensor})
        
        logits = outputs[0][0]
        probs = self._softmax(logits)
        
        return probs, None
    
    def _infer_pytorch(
        self,
        input_tensor: np.ndarray
    ) -> Tuple[np.ndarray, Optional[Dict]]:
        """Inferência PyTorch"""
        import torch
        
        with torch.no_grad():
            tensor = torch.from_numpy(input_tensor).to(self._device)
            output = self._model(tensor)
            
            probs = torch.softmax(output, dim=1)
            probs = probs[0].cpu().numpy()
        
        return probs, None
    
    def _simulate_classification(
        self,
        image: np.ndarray
    ) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Simula classificação baseada em heurísticas para demonstração.
        
        Na produção, substitua pelo modelo EfficientNet treinado.
        """
        h, w = image.shape[:2]
        
        # Extrai features simples para simulação
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Features baseadas em cor
        mean_h = np.mean(hsv[:, :, 0])
        mean_s = np.mean(hsv[:, :, 1])
        mean_v = np.mean(hsv[:, :, 2])
        
        # Features de textura (variância)
        texture_var = np.var(gray)
        
        # Features de forma (usando Canny)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        features = {
            "mean_hue": float(mean_h),
            "mean_saturation": float(mean_s),
            "mean_value": float(mean_v),
            "texture_variance": float(texture_var),
            "edge_density": float(edge_density)
        }
        
        # Heurísticas simples para simulação
        # (Em produção, o modelo aprenderia esses padrões)
        probs = np.zeros(self.NUM_CLASSES, dtype=np.float32)
        
        # Úlcera Venosa: geralmente mais avermelhada, bordas irregulares
        if mean_h < 20 and mean_s > 100:
            probs[EtiologyType.VENOUS_ULCER.value] = 0.4
        
        # Úlcera Arterial: mais pálida, bordas bem definidas
        if mean_v > 150 and edge_density > 0.1:
            probs[EtiologyType.ARTERIAL_ULCER.value] = 0.3
        
        # Pé Diabético: textura mais uniforme
        if texture_var < 2000:
            probs[EtiologyType.DIABETIC_FOOT.value] = 0.3
        
        # Lesão por Pressão: tons mais escuros (necrose comum)
        if mean_v < 100:
            probs[EtiologyType.PRESSURE_INJURY.value] = 0.35
        
        # Ferida Cirúrgica: bordas mais regulares, formato linear
        if edge_density > 0.15:
            probs[EtiologyType.SURGICAL_WOUND.value] = 0.25
        
        # Normaliza para somar 1
        probs += 0.1  # Base probability
        probs = probs / probs.sum()
        
        # Adiciona alguma aleatoriedade para simulação realista
        noise = np.random.uniform(-0.1, 0.1, size=self.NUM_CLASSES)
        probs = np.clip(probs + noise, 0.01, 1.0)
        probs = probs / probs.sum()
        
        return probs, features
    
    def _create_predictions(self, probs: np.ndarray) -> List[EtiologyPrediction]:
        """Cria lista de predições a partir das probabilidades"""
        predictions = []
        
        for i in range(self.NUM_CLASSES):
            predictions.append(EtiologyPrediction(
                class_id=i,
                class_name=ETIOLOGY_NAMES[i],
                confidence=float(probs[i]),
                description=ETIOLOGY_DESCRIPTIONS[i]
            ))
        
        return predictions
    
    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        """Softmax"""
        exp_x = np.exp(x - np.max(x))
        return exp_x / exp_x.sum()


class MultiModalClassifier:
    """
    Classificador multimodal que combina:
    - Imagem da ferida
    - Localização anatômica (texto/código)
    - Histórico do paciente
    
    Para uso futuro quando dados adicionais estiverem disponíveis.
    """
    
    def __init__(
        self,
        image_classifier: EtiologyClassifier,
        use_location: bool = False,
        use_history: bool = False
    ):
        self.image_classifier = image_classifier
        self.use_location = use_location
        self.use_history = use_history
    
    def classify(
        self,
        image: np.ndarray,
        location: Optional[str] = None,
        patient_history: Optional[Dict] = None
    ) -> EtiologyClassificationResult:
        """
        Classificação multimodal.
        
        Args:
            image: Imagem da ferida
            location: Localização anatômica (ex: "perna_inferior", "sacro")
            patient_history: Histórico do paciente (ex: {"diabetes": True})
        """
        # Classificação base por imagem
        result = self.image_classifier.classify(image)
        
        if not self.use_location and not self.use_history:
            return result
        
        # Ajusta probabilidades baseado em informações adicionais
        adjusted_probs = dict(result.probabilities)
        
        # Ajuste por localização
        if self.use_location and location:
            adjusted_probs = self._adjust_by_location(adjusted_probs, location)
        
        # Ajuste por histórico
        if self.use_history and patient_history:
            adjusted_probs = self._adjust_by_history(adjusted_probs, patient_history)
        
        # Renormaliza
        total = sum(adjusted_probs.values())
        adjusted_probs = {k: v / total for k, v in adjusted_probs.items()}
        
        # Recria resultado com probabilidades ajustadas
        # (Implementação simplificada - retorna resultado original por ora)
        return result
    
    def _adjust_by_location(
        self,
        probs: Dict[str, float],
        location: str
    ) -> Dict[str, float]:
        """Ajusta probabilidades baseado na localização"""
        adjusted = probs.copy()
        
        location_weights = {
            "perna_inferior": {
                ETIOLOGY_NAMES[EtiologyType.VENOUS_ULCER.value]: 1.5,
                ETIOLOGY_NAMES[EtiologyType.ARTERIAL_ULCER.value]: 1.2,
            },
            "pe": {
                ETIOLOGY_NAMES[EtiologyType.DIABETIC_FOOT.value]: 1.8,
                ETIOLOGY_NAMES[EtiologyType.ARTERIAL_ULCER.value]: 1.3,
            },
            "sacro": {
                ETIOLOGY_NAMES[EtiologyType.PRESSURE_INJURY.value]: 2.0,
            },
            "trocanter": {
                ETIOLOGY_NAMES[EtiologyType.PRESSURE_INJURY.value]: 2.0,
            },
            "calcaneo": {
                ETIOLOGY_NAMES[EtiologyType.PRESSURE_INJURY.value]: 1.8,
                ETIOLOGY_NAMES[EtiologyType.DIABETIC_FOOT.value]: 1.3,
            },
        }
        
        if location.lower() in location_weights:
            weights = location_weights[location.lower()]
            for etiology, weight in weights.items():
                if etiology in adjusted:
                    adjusted[etiology] *= weight
        
        return adjusted
    
    def _adjust_by_history(
        self,
        probs: Dict[str, float],
        history: Dict
    ) -> Dict[str, float]:
        """Ajusta probabilidades baseado no histórico"""
        adjusted = probs.copy()
        
        # Diabetes aumenta probabilidade de pé diabético
        if history.get("diabetes"):
            key = ETIOLOGY_NAMES[EtiologyType.DIABETIC_FOOT.value]
            if key in adjusted:
                adjusted[key] *= 2.0
        
        # Insuficiência venosa
        if history.get("insuficiencia_venosa"):
            key = ETIOLOGY_NAMES[EtiologyType.VENOUS_ULCER.value]
            if key in adjusted:
                adjusted[key] *= 2.0
        
        # Doença arterial periférica
        if history.get("doenca_arterial"):
            key = ETIOLOGY_NAMES[EtiologyType.ARTERIAL_ULCER.value]
            if key in adjusted:
                adjusted[key] *= 2.0
        
        # Acamado/cadeirante
        if history.get("acamado") or history.get("cadeirante"):
            key = ETIOLOGY_NAMES[EtiologyType.PRESSURE_INJURY.value]
            if key in adjusted:
                adjusted[key] *= 2.5
        
        return adjusted
