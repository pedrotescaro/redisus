# -*- coding: utf-8 -*-
"""
REDISUS - Módulo de Calibração e Filtragem de Confiança
========================================================

Baseado nas técnicas do notebook wounds_classifier_embeddings.ipynb:
  - Temperature Scaling para calibração de probabilidades
  - Confidence-threshold filtering (>0.95 melhora precision de 85→89%)
  - Expected Calibration Error (ECE) para avaliação de calibração

Uso:
    calibrator = ConfidenceCalibrator(temperature=1.5)
    calibrated = calibrator.calibrate(raw_logits)
    
    result = filter_by_confidence(probabilities, threshold=0.95)
    if result.needs_review:
        # Encaminhar para revisão especialista
"""

import numpy as np
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURAÇÕES DE CONFIANÇA
# ============================================================

# Thresholds otimizados baseados nos notebooks
CONFIDENCE_THRESHOLDS = {
    "high_confidence": 0.95,      # Muito alta — usado no notebook para filtragem
    "moderate_confidence": 0.80,  # Moderada — aceitar com cautela
    "low_confidence": 0.60,       # Baixa — requer revisão
    "reject_threshold": 0.40,     # Muito baixa — rejeitar classificação
}

# Pesos padrão por nível de confiança
CONFIDENCE_LEVELS = {
    "very_high": {"min": 0.95, "label": "Muito Alta", "action": "Aceitar"},
    "high": {"min": 0.80, "label": "Alta", "action": "Aceitar com monitoramento"},
    "moderate": {"min": 0.60, "label": "Moderada", "action": "Revisão recomendada"},
    "low": {"min": 0.40, "label": "Baixa", "action": "Revisão obrigatória"},
    "very_low": {"min": 0.0, "label": "Muito Baixa", "action": "Rejeitar classificação"},
}


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class CalibrationResult:
    """Resultado da calibração de confiança."""
    original_confidence: float
    calibrated_confidence: float
    confidence_level: str           # "very_high", "high", "moderate", "low", "very_low"
    confidence_label: str           # "Muito Alta", "Alta", etc.
    recommended_action: str         # "Aceitar", "Revisão recomendada", etc.
    needs_review: bool              # True se confiança abaixo do threshold moderado
    temperature: float              # Temperatura usada na calibração
    entropy: float                  # Entropia da distribuição (incerteza)
    margin: float                   # Margem entre top-2 classes (dispersão)

    def to_dict(self) -> Dict:
        """Serializa para dicionário."""
        return {
            "original_confidence": round(self.original_confidence, 4),
            "calibrated_confidence": round(self.calibrated_confidence, 4),
            "confidence_level": self.confidence_level,
            "confidence_label": self.confidence_label,
            "recommended_action": self.recommended_action,
            "needs_review": self.needs_review,
            "entropy": round(self.entropy, 4),
            "margin": round(self.margin, 4),
        }


@dataclass
class FilteredPrediction:
    """Resultado de uma predição filtrada por confiança."""
    class_index: int
    class_name: str
    confidence: float
    probabilities: np.ndarray
    passes_threshold: bool          # True se confiança >= threshold
    needs_review: bool              # True se confiança < moderate_threshold
    calibration: Optional[CalibrationResult] = None


# ============================================================
# TEMPERATURE SCALING
# ============================================================

class ConfidenceCalibrator:
    """
    Calibrador de confiança usando Temperature Scaling.
    
    Temperature Scaling ajusta as probabilidades do softmax dividindo
    os logits por um parâmetro T (temperatura):
      - T > 1: "suaviza" as probabilidades (menos overconfident)
      - T < 1: "afia" as probabilidades (mais confiante)
      - T = 1: sem alteração
    
    Referência: Guo et al., "On Calibration of Modern Neural Networks" (2017)
    """
    
    def __init__(self, temperature: float = 1.5):
        """
        Args:
            temperature: Parâmetro de temperatura (>1 reduz overconfidence)
        """
        if temperature <= 0:
            raise ValueError("Temperatura deve ser positiva")
        self.temperature = temperature
        logger.info(f"[Calibração] Inicializado com T={temperature:.2f}")
    
    def calibrate_logits(self, logits: np.ndarray) -> np.ndarray:
        """
        Aplica Temperature Scaling nos logits e retorna probabilidades calibradas.
        
        Args:
            logits: Array de logits [num_classes] ou [batch, num_classes]
            
        Returns:
            Probabilidades calibradas via softmax(logits / T)
        """
        scaled_logits = logits / self.temperature
        return _softmax(scaled_logits)
    
    def calibrate_probs(self, probabilities: np.ndarray) -> np.ndarray:
        """
        Aplica calibração em probabilidades já computadas.
        
        Converte prob → logit aproximado → temperature scaling → prob calibrada.
        
        Args:
            probabilities: Array de probabilidades [num_classes]
            
        Returns:
            Probabilidades recalibradas
        """
        # Evitar log(0)
        eps = 1e-10
        probs_clipped = np.clip(probabilities, eps, 1 - eps)
        
        # Prob → log-prob (pseudo-logits)
        log_probs = np.log(probs_clipped)
        
        # Temperature Scaling
        scaled = log_probs / self.temperature
        
        return _softmax(scaled)
    
    def analyze(
        self,
        probabilities: np.ndarray,
        class_names: Optional[List[str]] = None,
    ) -> CalibrationResult:
        """
        Analisa confiança completa de uma predição.
        
        Args:
            probabilities: Array de probabilidades [num_classes]
            class_names: Nomes das classes (opcional, para logging)
            
        Returns:
            CalibrationResult com métricas detalhadas
        """
        # Calibrar
        calibrated_probs = self.calibrate_probs(probabilities)
        
        original_conf = float(np.max(probabilities))
        calibrated_conf = float(np.max(calibrated_probs))
        
        # Entropia (incerteza) — normalizada por log(num_classes)
        entropy = compute_entropy(calibrated_probs)
        
        # Margem entre top-2 classes (dispersão)
        margin = compute_margin(calibrated_probs)
        
        # Determinar nível de confiança
        level, label, action = _get_confidence_level(calibrated_conf)
        
        needs_review = calibrated_conf < CONFIDENCE_THRESHOLDS["moderate_confidence"]
        
        result = CalibrationResult(
            original_confidence=original_conf,
            calibrated_confidence=calibrated_conf,
            confidence_level=level,
            confidence_label=label,
            recommended_action=action,
            needs_review=needs_review,
            temperature=self.temperature,
            entropy=entropy,
            margin=margin,
        )
        
        if class_names and needs_review:
            pred_idx = int(np.argmax(calibrated_probs))
            pred_name = class_names[pred_idx] if pred_idx < len(class_names) else f"class_{pred_idx}"
            logger.info(
                f"[Calibração] Revisão recomendada: {pred_name} "
                f"(conf={calibrated_conf:.3f}, entropy={entropy:.3f}, margin={margin:.3f})"
            )
        
        return result


# ============================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================

def filter_by_confidence(
    probabilities: np.ndarray,
    class_names: List[str],
    threshold: float = 0.95,
    calibrator: Optional[ConfidenceCalibrator] = None,
) -> FilteredPrediction:
    """
    Filtra uma predição baseado em threshold de confiança.
    
    Baseado na técnica do notebook wounds_classifier_embeddings.ipynb
    que mostra que filtrar predições com confiança > 0.95 melhora
    precision de ~85% para ~89%.
    
    Args:
        probabilities: Array de probabilidades [num_classes]
        class_names: Nomes das classes
        threshold: Threshold mínimo de confiança (default: 0.95 do notebook)
        calibrator: Calibrador opcional (aplica Temperature Scaling antes)
        
    Returns:
        FilteredPrediction com flags de filtragem
    """
    if calibrator is not None:
        calibrated = calibrator.calibrate_probs(probabilities)
        calibration_result = calibrator.analyze(probabilities, class_names)
    else:
        calibrated = probabilities
        calibration_result = None
    
    pred_idx = int(np.argmax(calibrated))
    confidence = float(calibrated[pred_idx])
    pred_name = class_names[pred_idx] if pred_idx < len(class_names) else f"class_{pred_idx}"
    
    passes = confidence >= threshold
    needs_review = confidence < CONFIDENCE_THRESHOLDS["moderate_confidence"]
    
    return FilteredPrediction(
        class_index=pred_idx,
        class_name=pred_name,
        confidence=confidence,
        probabilities=calibrated,
        passes_threshold=passes,
        needs_review=needs_review,
        calibration=calibration_result,
    )


def compute_entropy(probabilities: np.ndarray) -> float:
    """
    Calcula entropia normalizada de uma distribuição de probabilidades.
    
    Entropia alta → modelo incerto (probabilidades distribuídas).
    Entropia baixa → modelo confiante (uma classe dominante).
    
    Returns:
        Entropia normalizada [0, 1]
    """
    eps = 1e-10
    probs = np.clip(probabilities, eps, 1.0)
    entropy = -np.sum(probs * np.log(probs))
    
    # Normalizar pelo máximo teórico (distribuição uniforme)
    max_entropy = np.log(len(probabilities))
    if max_entropy > 0:
        entropy /= max_entropy
    
    return float(entropy)


def compute_margin(probabilities: np.ndarray) -> float:
    """
    Calcula margem entre as duas maiores probabilidades.
    
    Margem alta → modelo seguro da predição (top-1 muito maior que top-2).
    Margem baixa → modelo hesitando entre classes.
    
    Returns:
        Margem [0, 1] — diferença entre top-1 e top-2
    """
    if len(probabilities) < 2:
        return 1.0
    
    sorted_probs = np.sort(probabilities)[::-1]
    return float(sorted_probs[0] - sorted_probs[1])


def compute_ece(
    predictions: List[np.ndarray],
    labels: List[int],
    n_bins: int = 15,
) -> float:
    """
    Calcula Expected Calibration Error (ECE).
    
    ECE mede quão bem as probabilidades preditas refletem a acurácia real.
    ECE = 0 significa calibração perfeita.
    
    Args:
        predictions: Lista de arrays de probabilidades
        labels: Lista de labels verdadeiros (índices)
        n_bins: Número de bins para agrupamento
        
    Returns:
        ECE [0, 1]
    """
    if len(predictions) == 0:
        return 0.0
    
    confidences = []
    accuracies = []
    
    for pred, label in zip(predictions, labels):
        pred_idx = int(np.argmax(pred))
        conf = float(np.max(pred))
        correct = 1.0 if pred_idx == label else 0.0
        confidences.append(conf)
        accuracies.append(correct)
    
    confidences = np.array(confidences)
    accuracies = np.array(accuracies)
    
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    
    for i in range(n_bins):
        mask = (confidences > bin_boundaries[i]) & (confidences <= bin_boundaries[i + 1])
        if mask.sum() > 0:
            avg_conf = confidences[mask].mean()
            avg_acc = accuracies[mask].mean()
            bin_weight = mask.sum() / len(confidences)
            ece += bin_weight * abs(avg_acc - avg_conf)
    
    return float(ece)


# ============================================================
# FUNÇÕES AUXILIARES PRIVADAS
# ============================================================

def _softmax(x: np.ndarray) -> np.ndarray:
    """Softmax numericamente estável."""
    if x.ndim == 1:
        e_x = np.exp(x - np.max(x))
        return e_x / e_x.sum()
    else:
        e_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return e_x / e_x.sum(axis=-1, keepdims=True)


def _get_confidence_level(confidence: float) -> Tuple[str, str, str]:
    """Determina nível de confiança baseado nos thresholds."""
    for level, info in CONFIDENCE_LEVELS.items():
        if confidence >= info["min"]:
            return level, info["label"], info["action"]
    return "very_low", "Muito Baixa", "Rejeitar classificação"
