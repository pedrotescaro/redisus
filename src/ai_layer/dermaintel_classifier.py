"""
REDISUS - DermaIntel ViT Wound Classifier
==========================================

Integração com o modelo DermaIntel (Vision Transformer) do Hugging Face:
  PayamFard123/dermaintel-wound-classifier

Especificações:
  - Arquitetura: ViT-Base/16 (85.8M parâmetros)
  - Treinado em: Dataset clínico de feridas (7 classes)
  - Input: 224×224 RGB
  - Output: 7 classes

Classes DermaIntel → Mapeamento REDISUS (5 classes):
  Background       → (descartado)
  Diabetic Wound   → Pé Diabético (2)
  Pressure Wound   → Lesão por Pressão (3)
  Surgical Wound   → Ferida Cirúrgica (4)
  Venous Wound     → Úlcera Venosa (0)
  Traumatic Wound  → redistribuído proporcionalmente
  Normal Skin      → (descartado, adiciona a Background)
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger


# 7 classes do modelo DermaIntel
DERMAINTEL_CLASSES = [
    "Background",
    "Diabetic Wound",
    "Normal Skin",
    "Pressure Wound",
    "Surgical Wound",
    "Traumatic Wound",
    "Venous Wound",
]

# Mapeamento DermaIntel → REDISUS (class_id REDISUS)
DERMAINTEL_TO_REDISUS: Dict[str, int] = {
    "Venous Wound": 0,       # Úlcera Venosa
    "Diabetic Wound": 2,     # Pé Diabético
    "Pressure Wound": 3,     # Lesão por Pressão
    "Surgical Wound": 4,     # Ferida Cirúrgica
}

# Classes sem mapeamento direto (redistribuídas)
UNMAPPED_CLASSES = {"Background", "Normal Skin", "Traumatic Wound"}


@dataclass
class DermaIntelPrediction:
    """Resultado de uma predição DermaIntel."""
    class_name: str
    confidence: float
    class_index: int


@dataclass
class DermaIntelResult:
    """Resultado completo do classificador DermaIntel."""
    predictions: List[DermaIntelPrediction]
    raw_probabilities: Dict[str, float]
    inference_time_ms: float
    model_loaded: bool = True

    @property
    def top_prediction(self) -> DermaIntelPrediction:
        return self.predictions[0]

    def get_redisus_probabilities(self) -> Dict[int, float]:
        """Converte probabilidades DermaIntel → REDISUS 5 classes."""
        redisus_probs = {i: 0.0 for i in range(5)}
        unmapped_total = 0.0

        for cls_name, prob in self.raw_probabilities.items():
            if cls_name in DERMAINTEL_TO_REDISUS:
                rid = DERMAINTEL_TO_REDISUS[cls_name]
                redisus_probs[rid] += prob
            else:
                unmapped_total += prob

        # Redistribui classes não mapeadas proporcionalmente
        mapped_total = sum(redisus_probs.values())
        if mapped_total > 0 and unmapped_total > 0:
            for rid in redisus_probs:
                share = redisus_probs[rid] / mapped_total
                redisus_probs[rid] += unmapped_total * share

        # Normaliza
        total = sum(redisus_probs.values())
        if total > 0:
            redisus_probs = {k: v / total for k, v in redisus_probs.items()}

        return redisus_probs


class DermaIntelClassifier:
    """
    Classificador de feridas usando DermaIntel ViT (Hugging Face).

    Fallback: simulação por heurísticas HSV quando o modelo não estiver disponível.
    """

    MODEL_ID = "PayamFard123/dermaintel-wound-classifier"
    INPUT_SIZE = (224, 224)
    NUM_CLASSES = 7

    def __init__(self):
        self._processor = None
        self._model = None
        self._device = None
        self._loaded = False

    # ------------------------------------------------------------------
    def load_model(self) -> bool:
        """Carrega o modelo DermaIntel do Hugging Face."""
        try:
            from transformers import ViTForImageClassification, ViTImageProcessor
            import torch

            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            logger.info(f"DermaIntel: carregando {self.MODEL_ID} em {self._device}…")

            self._processor = ViTImageProcessor.from_pretrained(self.MODEL_ID)
            self._model = ViTForImageClassification.from_pretrained(self.MODEL_ID)
            self._model.to(self._device)
            self._model.eval()

            self._loaded = True
            logger.info("DermaIntel: modelo carregado com sucesso")
            return True

        except Exception as e:
            logger.warning(f"DermaIntel: falha ao carregar modelo ({e}). Usando simulação.")
            self._loaded = False
            return False

    # ------------------------------------------------------------------
    def classify(self, image: np.ndarray) -> DermaIntelResult:
        """Classifica uma imagem de ferida."""
        if self._loaded:
            return self._infer(image)
        return self._simulate(image)

    # ------------------------------------------------------------------
    def _infer(self, image: np.ndarray) -> DermaIntelResult:
        """Inferência real com o modelo DermaIntel."""
        import torch

        start = time.perf_counter()

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        from PIL import Image as PILImage
        pil_img = PILImage.fromarray(rgb)

        inputs = self._processor(images=pil_img, return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)
            logits = outputs.logits[0]
            probs = torch.softmax(logits, dim=0).cpu().numpy()

        elapsed_ms = (time.perf_counter() - start) * 1000
        return self._build_result(probs, elapsed_ms, model_loaded=True)

    # ------------------------------------------------------------------
    def _simulate(self, image: np.ndarray) -> DermaIntelResult:
        """Simulação por heurísticas de cor HSV."""
        start = time.perf_counter()

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

        scores = np.zeros(self.NUM_CLASSES, dtype=np.float32)

        # Background (baixa saturação, alta luminância)
        bg_mask = (s < 30) & (v > 200)
        scores[0] = np.mean(bg_mask) * 0.8

        # Diabetic (tons amarelados/acinzentados)
        diab_mask = ((h >= 15) & (h <= 35) & (s > 40) & (v > 80))
        scores[1] = np.mean(diab_mask) * 0.9

        # Normal Skin
        skin_mask = ((h >= 5) & (h <= 25) & (s >= 30) & (s <= 170) & (v >= 80))
        scores[2] = np.mean(skin_mask) * 0.5

        # Pressure (tons escuros avermelhados/roxos)
        press_mask = ((h >= 140) | (h <= 10)) & (v < 120) & (s > 40)
        scores[3] = np.mean(press_mask) * 0.85

        # Surgical (bordas regulares, vermelho + rosa)
        surg_mask = ((h <= 10) | (h >= 170)) & (s > 60) & (v > 100)
        scores[4] = np.mean(surg_mask) * 0.7

        # Traumatic (variado, alta textura)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        texture_var = np.var(gray) / 10000.0
        scores[5] = min(texture_var, 0.6)

        # Venous (avermelhado com fundo pálido)
        ven_mask = ((h <= 15) & (s > 80) & (v > 60))
        scores[6] = np.mean(ven_mask) * 0.9

        # Normaliza via softmax
        scores = scores + 0.05
        exp_s = np.exp(scores - np.max(scores))
        probs = exp_s / exp_s.sum()

        elapsed_ms = (time.perf_counter() - start) * 1000
        return self._build_result(probs, elapsed_ms, model_loaded=False)

    # ------------------------------------------------------------------
    def _build_result(
        self, probs: np.ndarray, elapsed_ms: float, model_loaded: bool
    ) -> DermaIntelResult:
        raw_probs: Dict[str, float] = {}
        predictions: List[DermaIntelPrediction] = []

        for i, cls in enumerate(DERMAINTEL_CLASSES):
            p = float(probs[i])
            raw_probs[cls] = p
            predictions.append(DermaIntelPrediction(cls, p, i))

        predictions.sort(key=lambda x: x.confidence, reverse=True)

        return DermaIntelResult(
            predictions=predictions,
            raw_probabilities=raw_probs,
            inference_time_ms=elapsed_ms,
            model_loaded=model_loaded,
        )

    @property
    def is_loaded(self) -> bool:
        return self._loaded
