from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
from loguru import logger

from .resnet_wound_classifier import TwoStageWoundClassifier

_BASE_DIR = Path(__file__).resolve().parent.parent.parent

_WOUND_TYPE_TO_ETIOLOGY = {
    "Diabetic Wounds": "diabetic_foot",
    "Pressure Wounds": "pressure_injury",
    "Venous Wounds": "venous_ulcer",
    "Normal": "unspecified_wound",
    "Wound": "unspecified_wound",
}


@dataclass(slots=True)
class RuntimeModelDescriptor:
    id: str
    task: str
    artifact: str
    status: str
    framework: str | None = None
    version: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    metadata_path: str | None = None
    thresholds: dict[str, float] = field(default_factory=dict)
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task": self.task,
            "artifact": self.artifact,
            "status": self.status,
            "framework": self.framework,
            "version": self.version,
            "metrics": self.metrics,
            "metadata_path": self.metadata_path,
            "thresholds": self.thresholds,
            "notes": self.notes,
        }


class ClinicalMLService:
    """Runtime bridge between model artifacts and the clinical inference pipeline."""

    def __init__(self):
        self._classifier: TwoStageWoundClassifier | None = None
        self._classifier_attempted = False
        self._registry = self._build_registry()

    def _load_metadata(self, relative_path: str) -> dict[str, Any]:
        path = _BASE_DIR / relative_path
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"Falha ao carregar metadata de modelo {path}: {exc}")
            return {}

    def _build_registry(self) -> list[RuntimeModelDescriptor]:
        v3_metadata = self._load_metadata("models/wound_classifier_v2/model_metadata_v2.json")
        v1_metadata = self._load_metadata("models/wound_classifier/model_metadata.json")
        registry: list[RuntimeModelDescriptor] = [
            RuntimeModelDescriptor(
                id="heal-two-stage-resnet50",
                task="clinical-wound-triage",
                artifact="models/wound_classifier_v2/modelo_estagio1.pth + modelo_estagio2_semAugmentation.pth",
                status="runtime-preferred",
                framework="PyTorch/torchvision",
                version="2026-04-07-resnet50-two-stage",
                thresholds={"expert_review": 0.80, "high_confidence": 0.95},
                notes="Pipeline clínico com confidence margin, entropy e expert review.",
            ),
            RuntimeModelDescriptor(
                id="wound-classifier-v3",
                task="wound-image-classification",
                artifact="models/wound_classifier_v2/wound_classifier_v2.pt",
                status="candidate",
                framework=str(v3_metadata.get("framework") or "PyTorch"),
                version=str(v3_metadata.get("version") or "3.0.0"),
                metrics=dict(v3_metadata.get("metrics") or {}),
                metadata_path="models/wound_classifier_v2/model_metadata_v2.json",
                thresholds={"top1_accept": 0.70, "top3_review": 0.85},
                notes="Baseline consolidado do repositório atual.",
            ),
            RuntimeModelDescriptor(
                id="wound-classifier-v1",
                task="wound-image-classification",
                artifact="models/wound_classifier/wound_classifier_final.keras",
                status="legacy",
                framework=str(v1_metadata.get("framework") or "TensorFlow/Keras"),
                version=str(v1_metadata.get("version") or "1.0.0"),
                metrics=dict(v1_metadata.get("metrics") or {}),
                metadata_path="models/wound_classifier/model_metadata.json",
                notes="Baseline legado mantido para rastreabilidade.",
            ),
        ]
        return registry

    def describe_registry(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self._registry]

    def preferred_descriptor(self) -> RuntimeModelDescriptor:
        return next((item for item in self._registry if item.status == "runtime-preferred"), self._registry[0])

    def _get_classifier(self) -> TwoStageWoundClassifier | None:
        if self._classifier_attempted:
            return self._classifier

        self._classifier_attempted = True
        try:
            classifier = TwoStageWoundClassifier()
        except Exception as exc:
            logger.warning(f"Falha ao inicializar classificador clínico: {exc}")
            self._classifier = None
            return None

        if not getattr(classifier, "available", False):
            self._classifier = None
            return None

        self._classifier = classifier
        return self._classifier

    def _select_image(self, evaluation: dict[str, Any]) -> dict[str, Any] | None:
        images = evaluation.get("images")
        if not isinstance(images, list):
            return None
        clinical_images = [
            image
            for image in images
            if str((image or {}).get("image_role") or "clinical").strip().lower() in {"clinical", "frontal", "measurement"}
        ]
        return (clinical_images or images)[-1] if (clinical_images or images) else None

    @staticmethod
    def _heuristic_tissue(area_cm2: float, pain_score: float) -> dict[str, float]:
        if area_cm2 >= 15 or pain_score >= 7:
            return {"granulation": 42.0, "slough": 34.0, "necrosis": 24.0}
        if area_cm2 >= 8 or pain_score >= 4:
            return {"granulation": 58.0, "slough": 28.0, "necrosis": 14.0}
        return {"granulation": 72.0, "slough": 20.0, "necrosis": 8.0}

    def _fallback_output(self, evaluation: dict[str, Any]) -> dict[str, Any]:
        area = float(evaluation.get("wound_area_cm2") or 0.0)
        pain = float(evaluation.get("pain_score") or 0.0)
        if area >= 15:
            etiology = "pressure_injury"
        elif area >= 8:
            etiology = "venous_ulcer"
        else:
            etiology = "diabetic_foot"

        follow_up_hint = 3 if area >= 10 or pain >= 6 else 7
        return {
            "etiology": etiology,
            "confidence": 0.68,
            "tissue_percentages": self._heuristic_tissue(area, pain),
            "wound_area_cm2": area,
            "diagnosis_summary": "Inferência heurística operacional até revisão clínica do modelo.",
            "recommendations": [
                "Validar o resultado clínico manualmente antes de decisão terapêutica.",
                f"Agendar revisão clínica em até {follow_up_hint} dia(s).",
            ],
            "fallback_used": True,
            "needs_expert_review": True,
            "confidence_level": "low",
            "metadata": {
                "source": "clinical-heuristic-fallback",
                "registry": self.describe_registry(),
            },
        }

    def _classifier_output(self, evaluation: dict[str, Any], image_path: Path) -> dict[str, Any] | None:
        classifier = self._get_classifier()
        if classifier is None:
            return None

        image = cv2.imread(str(image_path))
        if image is None:
            return None

        result = classifier.predict(image)
        if not getattr(result, "is_wound", True):
            return None

        result_dict = result.to_dict()
        wound_type = (
            ((result_dict.get("stage2") or {}).get("wound_type"))
            or result_dict.get("final_class")
            or "Wound"
        )
        etiology = _WOUND_TYPE_TO_ETIOLOGY.get(str(wound_type), "unspecified_wound")
        confidence = float(result_dict.get("final_confidence") or 0.0)
        action = classifier.get_clinical_action(str(wound_type))
        return {
            "etiology": etiology,
            "confidence": confidence,
            "tissue_percentages": self._heuristic_tissue(
                float(evaluation.get("wound_area_cm2") or 0.0),
                float(evaluation.get("pain_score") or 0.0),
            ),
            "wound_area_cm2": float(evaluation.get("wound_area_cm2") or 0.0),
            "diagnosis_summary": (
                f"{result_dict.get('final_class_pt') or wound_type} detectada com confiança {confidence:.2f}."
            ),
            "recommendations": [action] if action else ["Revisar achados clínicos no contexto do paciente."],
            "fallback_used": False,
            "needs_expert_review": bool(result_dict.get("needs_expert_review")),
            "confidence_level": result_dict.get("confidence_level"),
            "confidence_entropy": result_dict.get("confidence_entropy"),
            "confidence_margin": result_dict.get("confidence_margin"),
            "metadata": {
                "source": "heal-two-stage-resnet50",
                "runtime_result": result_dict,
                "image_path": str(image_path),
                "registry": self.describe_registry(),
            },
        }

    def run_inference(self, evaluation: dict[str, Any]) -> dict[str, Any]:
        descriptor = self.preferred_descriptor()
        image_record = self._select_image(evaluation)
        if image_record:
            image_path = Path(str(image_record.get("image_path") or ""))
            if image_path.exists():
                raw_output = self._classifier_output(evaluation, image_path)
                if raw_output is not None:
                    return {
                        "raw_output": raw_output,
                        "model_version": descriptor.version or descriptor.id,
                        "model_descriptor": descriptor.to_dict(),
                    }

        fallback_output = self._fallback_output(evaluation)
        return {
            "raw_output": fallback_output,
            "model_version": descriptor.version or descriptor.id,
            "model_descriptor": descriptor.to_dict(),
        }
