from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn.functional as F
    from torchvision import models, transforms
    from PIL import Image

    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

PRESSURE_STAGE_CODES = ["stage_1", "stage_2", "stage_3", "stage_4"]
PRESSURE_STAGE_LABELS_PT = {
    "stage_1": "Lesao por Pressao - Estagio 1",
    "stage_2": "Lesao por Pressao - Estagio 2",
    "stage_3": "Lesao por Pressao - Estagio 3",
    "stage_4": "Lesao por Pressao - Estagio 4",
}
PRESSURE_STAGE_ACTIONS = {
    "stage_1": [
        "Priorizar alivio de pressao e reposicionamento frequente.",
        "Monitorar hiperemia e integridade da pele em cada troca de decubito.",
    ],
    "stage_2": [
        "Manter leito umido protegido e reduzir friccao/cisalhamento.",
        "Documentar perda parcial de espessura e reavaliar em ate 72h.",
    ],
    "stage_3": [
        "Avaliar profundidade, tunelizacao e necessidade de desbridamento.",
        "Intensificar vigilancia para exsudato, esfacelo e sinais de infeccao.",
    ],
    "stage_4": [
        "Acionar avaliacao especializada imediata para perda tecidual profunda.",
        "Investigar necrose/esfacelo extenso e exposicao de estruturas profundas.",
    ],
}


@dataclass(slots=True)
class PressureInjuryVisualSignals:
    red_ratio: float
    yellow_ratio: float
    dark_ratio: float
    pink_ratio: float
    edge_density: float
    brightness_mean: float
    brightness_std: float
    lesion_fraction: float

    def to_dict(self) -> dict[str, float]:
        return {
            "red_ratio": round(self.red_ratio, 4),
            "yellow_ratio": round(self.yellow_ratio, 4),
            "dark_ratio": round(self.dark_ratio, 4),
            "pink_ratio": round(self.pink_ratio, 4),
            "edge_density": round(self.edge_density, 4),
            "brightness_mean": round(self.brightness_mean, 4),
            "brightness_std": round(self.brightness_std, 4),
            "lesion_fraction": round(self.lesion_fraction, 4),
        }


@dataclass(slots=True)
class PressureInjuryStagePrediction:
    stage_code: str
    stage_label_pt: str
    confidence: float
    probabilities: dict[str, float]
    source: str
    needs_expert_review: bool
    confidence_margin: float
    visual_signals: PressureInjuryVisualSignals
    considerations: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    model_available: bool = False
    model_version: str = "pressure-injury-stage-heuristic-v1"

    def to_dict(self) -> dict[str, Any]:
        top_predictions = sorted(
            (
                {
                    "stage_code": stage_code,
                    "stage_label_pt": PRESSURE_STAGE_LABELS_PT[stage_code],
                    "confidence": round(confidence, 4),
                }
                for stage_code, confidence in self.probabilities.items()
            ),
            key=lambda item: item["confidence"],
            reverse=True,
        )
        return {
            "stage_code": self.stage_code,
            "stage_label_pt": self.stage_label_pt,
            "confidence": round(self.confidence, 4),
            "probabilities": {key: round(value, 4) for key, value in self.probabilities.items()},
            "source": self.source,
            "needs_expert_review": self.needs_expert_review,
            "confidence_margin": round(self.confidence_margin, 4),
            "visual_signals": self.visual_signals.to_dict(),
            "considerations": list(self.considerations),
            "recommended_actions": list(self.recommended_actions),
            "model_available": self.model_available,
            "model_version": self.model_version,
            "top_predictions": top_predictions,
        }


class PressureInjuryStageClassifier:
    """Classificador especializado de estagio de lesao por pressao com fallback heuristico."""

    INPUT_SIZE = 224

    def __init__(
        self,
        *,
        weights_path: Optional[str] = None,
        metadata_path: Optional[str] = None,
        device: Optional[str] = None,
        enable_pairwise_calibration: bool = True,
    ):
        self.available = False
        self._device = None
        self._model = None
        self._transform = None
        self._weights_path = Path(weights_path) if weights_path else self._default_weights_path()
        self._metadata_path = Path(metadata_path) if metadata_path else self._default_metadata_path()
        self._metadata = self._load_metadata()
        self._enable_pairwise_calibration = enable_pairwise_calibration
        calibration = self._metadata.get("stage34_calibration") if enable_pairwise_calibration else None
        self._stage34_calibration = calibration if calibration and calibration.get("enabled", False) else None
        self.model_version = str(self._metadata.get("version") or "pressure-injury-stage-heuristic-v1")

        if not _TORCH_AVAILABLE:
            return

        try:
            self._device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
            self._transform = transforms.Compose(
                [
                    transforms.Resize((self.INPUT_SIZE, self.INPUT_SIZE)),
                    transforms.ToTensor(),
                    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
                ]
            )
            self._load_model()
        except Exception as exc:
            logger.warning(f"Falha ao inicializar classificador especializado de LP: {exc}")
            self.available = False

    @staticmethod
    def _default_weights_path() -> Path:
        return Path(__file__).resolve().parents[2] / "models" / "pressure_injury_stage_classifier" / "pressure_injury_stage_resnet50.pth"

    @staticmethod
    def _default_metadata_path() -> Path:
        return Path(__file__).resolve().parents[2] / "models" / "pressure_injury_stage_classifier" / "model_metadata.json"

    def _load_metadata(self) -> dict[str, Any]:
        if not self._metadata_path.exists():
            return {}
        try:
            return json.loads(self._metadata_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"Falha ao ler metadata do classificador LP: {exc}")
            return {}

    def _build_model(self):
        model = models.resnet50(weights=None)
        model.fc = torch.nn.Sequential(
            torch.nn.Linear(model.fc.in_features, 256),
            torch.nn.ReLU(inplace=True),
            torch.nn.Dropout(0.3),
            torch.nn.Linear(256, len(PRESSURE_STAGE_CODES)),
        )
        return model

    def _load_model(self) -> None:
        if not self._weights_path.exists():
            return
        model = self._build_model()
        state_dict = torch.load(str(self._weights_path), map_location=self._device, weights_only=True)
        model.load_state_dict(state_dict)
        model.to(self._device)
        model.eval()
        self._model = model
        self.available = True

    @staticmethod
    def _softmax(scores: dict[str, float]) -> dict[str, float]:
        values = np.array([scores[stage_code] for stage_code in PRESSURE_STAGE_CODES], dtype=np.float32)
        shifted = values - values.max()
        exp = np.exp(shifted)
        probs = exp / exp.sum()
        return {
            stage_code: float(probs[index])
            for index, stage_code in enumerate(PRESSURE_STAGE_CODES)
        }

    @staticmethod
    def stage34_feature_names() -> list[str]:
        return [
            "p_stage_1",
            "p_stage_2",
            "p_stage_3",
            "p_stage_4",
            "p4_minus_p3",
            "p3_minus_p4",
            "red_ratio",
            "yellow_ratio",
            "dark_ratio",
            "pink_ratio",
            "edge_density",
            "brightness_std",
            "lesion_fraction",
            "yellow_minus_dark",
            "dark_to_yellow_ratio",
        ]

    @staticmethod
    def stage34_feature_vector(
        probabilities: dict[str, float],
        signals: PressureInjuryVisualSignals,
    ) -> list[float]:
        yellow = float(signals.yellow_ratio)
        dark = float(signals.dark_ratio)
        p3 = float(probabilities.get("stage_3", 0.0))
        p4 = float(probabilities.get("stage_4", 0.0))
        return [
            float(probabilities.get("stage_1", 0.0)),
            float(probabilities.get("stage_2", 0.0)),
            p3,
            p4,
            p4 - p3,
            p3 - p4,
            float(signals.red_ratio),
            yellow,
            dark,
            float(signals.pink_ratio),
            float(signals.edge_density),
            float(signals.brightness_std),
            float(signals.lesion_fraction),
            yellow - dark,
            dark / max(yellow, 1e-4),
        ]

    @staticmethod
    def _sigmoid(value: float) -> float:
        value = float(np.clip(value, -40.0, 40.0))
        return float(1.0 / (1.0 + np.exp(-value)))

    def _stage34_pair_probability(
        self,
        probabilities: dict[str, float],
        signals: PressureInjuryVisualSignals,
    ) -> float | None:
        calibration = self._stage34_calibration
        if not calibration:
            return None
        try:
            weights = np.array(calibration["weights"], dtype=np.float32)
            bias = float(calibration.get("bias", 0.0))
            mean = np.array(calibration.get("feature_mean", [0.0] * len(weights)), dtype=np.float32)
            scale = np.array(calibration.get("feature_scale", [1.0] * len(weights)), dtype=np.float32)
            features = np.array(self.stage34_feature_vector(probabilities, signals), dtype=np.float32)
            if len(features) != len(weights):
                return None
            normalized = (features - mean) / np.where(scale == 0, 1.0, scale)
            return self._sigmoid(float(np.dot(normalized, weights) + bias))
        except Exception as exc:
            logger.warning(f"Falha ao aplicar calibracao stage_3/stage_4: {exc}")
            return None

    def _apply_stage34_calibration(
        self,
        probabilities: dict[str, float],
        signals: PressureInjuryVisualSignals,
    ) -> tuple[dict[str, float], bool]:
        pair_mass = float(probabilities.get("stage_3", 0.0) + probabilities.get("stage_4", 0.0))
        if pair_mass < 0.20:
            return probabilities, False
        pair_probability_stage4 = self._stage34_pair_probability(probabilities, signals)
        if pair_probability_stage4 is None:
            return probabilities, False

        calibrated = dict(probabilities)
        calibrated["stage_4"] = pair_mass * pair_probability_stage4
        calibrated["stage_3"] = pair_mass * (1.0 - pair_probability_stage4)
        total = sum(calibrated.values()) or 1.0
        calibrated = {stage: float(value / total) for stage, value in calibrated.items()}
        return calibrated, True

    @staticmethod
    def _extract_visual_signals(image_bgr: np.ndarray) -> PressureInjuryVisualSignals:
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

        red_mask = (
            cv2.inRange(hsv, np.array([0, 70, 60]), np.array([10, 255, 255]))
            | cv2.inRange(hsv, np.array([165, 70, 60]), np.array([180, 255, 255]))
        )
        yellow_mask = cv2.inRange(hsv, np.array([15, 40, 90]), np.array([40, 255, 255]))
        dark_mask = cv2.inRange(gray, 0, 55)
        pink_mask = (
            cv2.inRange(hsv, np.array([0, 10, 170]), np.array([12, 80, 255]))
            | cv2.inRange(hsv, np.array([165, 10, 170]), np.array([180, 80, 255]))
        )
        edges = cv2.Canny(gray, 60, 160)

        total_pixels = float(gray.size or 1)
        red_ratio = float(np.count_nonzero(red_mask)) / total_pixels
        yellow_ratio = float(np.count_nonzero(yellow_mask)) / total_pixels
        dark_ratio = float(np.count_nonzero(dark_mask)) / total_pixels
        pink_ratio = float(np.count_nonzero(pink_mask)) / total_pixels
        lesion_fraction = min(1.0, red_ratio + yellow_ratio + dark_ratio + pink_ratio)
        edge_density = float(np.count_nonzero(edges)) / total_pixels
        return PressureInjuryVisualSignals(
            red_ratio=red_ratio,
            yellow_ratio=yellow_ratio,
            dark_ratio=dark_ratio,
            pink_ratio=pink_ratio,
            edge_density=edge_density,
            brightness_mean=float(np.mean(gray)) / 255.0,
            brightness_std=float(np.std(gray)) / 255.0,
            lesion_fraction=lesion_fraction,
        )

    @staticmethod
    def _heuristic_probabilities(
        signals: PressureInjuryVisualSignals,
        evaluation_context: Optional[dict[str, Any]] = None,
    ) -> dict[str, float]:
        area = float((evaluation_context or {}).get("wound_area_cm2") or 0.0)
        pain = float((evaluation_context or {}).get("pain_score") or 0.0)
        scores = {
            "stage_1": 1.0 + signals.pink_ratio * 8.0 + max(0.0, 0.14 - signals.dark_ratio) * 3.0,
            "stage_2": 1.0 + signals.red_ratio * 7.0 + signals.edge_density * 3.0,
            "stage_3": 1.0 + signals.yellow_ratio * 9.0 + signals.brightness_std * 2.5,
            "stage_4": 1.0 + signals.dark_ratio * 12.0 + signals.edge_density * 1.5,
        }
        if area >= 10:
            scores["stage_3"] += 0.6
        if area >= 20:
            scores["stage_4"] += 0.8
        if pain >= 5:
            scores["stage_3"] += 0.4
        if pain >= 7:
            scores["stage_4"] += 0.5
        if signals.yellow_ratio > 0.12:
            scores["stage_3"] += 0.7
        if signals.dark_ratio > 0.10:
            scores["stage_4"] += 1.0
        if signals.pink_ratio > 0.20 and signals.dark_ratio < 0.04:
            scores["stage_1"] += 0.8
        return PressureInjuryStageClassifier._softmax(scores)

    def _predict_model_probabilities(self, image_bgr: np.ndarray) -> dict[str, float] | None:
        if not self.available or self._model is None or not _TORCH_AVAILABLE:
            return None
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)
        tensor = self._transform(pil_image).unsqueeze(0).to(self._device)
        with torch.no_grad():
            logits = self._model(tensor)
            probs = F.softmax(logits, dim=1).squeeze(0).detach().cpu().numpy()
        return {
            stage_code: float(probs[index])
            for index, stage_code in enumerate(PRESSURE_STAGE_CODES)
        }

    @staticmethod
    def _build_considerations(
        probabilities: dict[str, float],
        signals: PressureInjuryVisualSignals,
        evaluation_context: Optional[dict[str, Any]],
        source: str,
    ) -> list[str]:
        considerations: list[str] = [
            f"Fonte da decisão: {source}.",
            (
                "Sinais visuais considerados: proporção de tons rosados, vermelhos, amarelados e escuros, "
                "densidade de bordas/textura e variação global de luminosidade."
            ),
        ]
        if "stage34-calibrated" in source:
            considerations.append("Calibracao especifica stage_3/stage_4 aplicada para reduzir confusao entre perda profunda e muito profunda.")
        top_stage = max(probabilities, key=probabilities.get)
        if signals.pink_ratio >= 0.18:
            considerations.append("Predomínio de tons rosados claros sugere acometimento mais superficial.")
        if signals.red_ratio >= 0.16:
            considerations.append("Predomínio de vermelho vivo sugere perda tecidual superficial com leito exposto.")
        if signals.yellow_ratio >= 0.10:
            considerations.append("Presença relevante de tons amarelados sugere esfacelo/fibrina e maior profundidade.")
        if signals.dark_ratio >= 0.08:
            considerations.append("Presença de áreas escuras sugere necrose ou dano profundo e eleva suspeita de estágio avançado.")
        if signals.edge_density >= 0.12:
            considerations.append("Maior densidade de bordas/textura sugere irregularidade e heterogeneidade do leito.")
        if evaluation_context:
            area = float(evaluation_context.get("wound_area_cm2") or 0.0)
            pain = float(evaluation_context.get("pain_score") or 0.0)
            considerations.append(f"Contexto estruturado considerado: area {area:.2f} cm² e dor {pain:.1f}/10.")
        considerations.append(f"Estágio com maior probabilidade: {PRESSURE_STAGE_LABELS_PT[top_stage]}.")
        return considerations

    def predict(
        self,
        image_bgr: np.ndarray,
        *,
        evaluation_context: Optional[dict[str, Any]] = None,
    ) -> PressureInjuryStagePrediction:
        signals = self._extract_visual_signals(image_bgr)
        heuristic_probabilities = self._heuristic_probabilities(signals, evaluation_context)
        model_probabilities = self._predict_model_probabilities(image_bgr)

        if model_probabilities:
            probabilities = {
                stage_code: round(model_probabilities[stage_code] * 0.8 + heuristic_probabilities[stage_code] * 0.2, 6)
                for stage_code in PRESSURE_STAGE_CODES
            }
            source = "model+heuristic"
        else:
            probabilities = heuristic_probabilities
            source = "heuristic"

        probabilities, stage34_calibrated = self._apply_stage34_calibration(probabilities, signals)
        if stage34_calibrated:
            source = f"{source}+stage34-calibrated"

        sorted_stages = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
        stage_code, confidence = sorted_stages[0]
        second_confidence = sorted_stages[1][1] if len(sorted_stages) > 1 else 0.0
        confidence_margin = float(confidence) - float(second_confidence)
        stage34_case = stage_code in {"stage_3", "stage_4"} or {
            sorted_stages[0][0],
            sorted_stages[1][0],
        } == {"stage_3", "stage_4"}
        needs_expert_review = (
            source == "heuristic"
            or confidence < 0.82
            or confidence_margin < 0.15
            or (stage34_case and (confidence < 0.88 or confidence_margin < 0.25))
        )
        considerations = self._build_considerations(probabilities, signals, evaluation_context, source)
        return PressureInjuryStagePrediction(
            stage_code=stage_code,
            stage_label_pt=PRESSURE_STAGE_LABELS_PT[stage_code],
            confidence=float(confidence),
            probabilities={stage: float(prob) for stage, prob in probabilities.items()},
            source=source,
            needs_expert_review=needs_expert_review,
            confidence_margin=confidence_margin,
            visual_signals=signals,
            considerations=considerations,
            recommended_actions=list(PRESSURE_STAGE_ACTIONS[stage_code]),
            model_available=self.available,
            model_version=self.model_version,
        )
