from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
from loguru import logger

from packages.clinical_domain.workflow import DEFAULT_MODEL_VERSION

from .pressure_injury_stage_classifier import (
    PRESSURE_STAGE_ACTIONS,
    PressureInjuryStageClassifier,
    PressureInjuryStagePrediction,
)
from .resnet_wound_classifier import TwoStageWoundClassifier

_BASE_DIR = Path(__file__).resolve().parent.parent.parent

_WOUND_TYPE_TO_ETIOLOGY = {
    "Diabetic Wounds": "diabetic_foot",
    "Pressure Wounds": "pressure_injury",
    "Venous Wounds": "venous_ulcer",
    "Normal": "unspecified_wound",
    "Wound": "unspecified_wound",
}

_PRESSURE_HINT_TOKENS = {
    "pressure_injury",
    "pressure_wound",
    "pressure_wounds",
    "lesao_por_pressao",
    "lesao_pressao",
    "ulcera_pressao",
}


def _normalize_etiology_hint(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _looks_like_pressure_injury(value: Any) -> bool:
    normalized = _normalize_etiology_hint(value)
    return normalized in _PRESSURE_HINT_TOKENS or "pressure" in normalized or "pressao" in normalized


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(text)
    return deduped


def merge_pressure_injury_stage_assessment(
    raw_output: dict[str, Any],
    stage_prediction: PressureInjuryStagePrediction,
) -> dict[str, Any]:
    merged = dict(raw_output or {})
    base_confidence = float(merged.get("confidence") or 0.0)
    specialized_confidence = float(stage_prediction.confidence or 0.0)
    combined_confidence = specialized_confidence if base_confidence <= 0 else (base_confidence + specialized_confidence) / 2.0

    merged["etiology"] = "pressure_injury"
    merged["confidence"] = round(combined_confidence, 4)
    merged["needs_expert_review"] = bool(merged.get("needs_expert_review")) or stage_prediction.needs_expert_review
    if not merged.get("confidence_margin"):
        merged["confidence_margin"] = round(stage_prediction.confidence_margin, 4)

    base_summary = str(merged.get("diagnosis_summary") or "Lesao por pressao identificada.")
    merged["diagnosis_summary"] = (
        f"{base_summary} Avaliacao especializada de LP sugere "
        f"{stage_prediction.stage_label_pt.lower()} com confianca {stage_prediction.confidence:.2f}."
    )

    recommendations = _dedupe_strings(
        list(stage_prediction.recommended_actions)
        + list(PRESSURE_STAGE_ACTIONS.get(stage_prediction.stage_code, []))
        + [str(item) for item in merged.get("recommendations") or []]
    )
    merged["recommendations"] = recommendations[:5]

    metadata = dict(merged.get("metadata") or {})
    metadata["pressure_injury_stage_assessment"] = stage_prediction.to_dict()
    merged["metadata"] = metadata
    return merged


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
        self._pressure_classifier: PressureInjuryStageClassifier | None = None
        self._pressure_classifier_attempted = False
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
        pressure_metadata = self._load_metadata("models/pressure_injury_stage_classifier/model_metadata.json")
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
            RuntimeModelDescriptor(
                id="pressure-injury-stage-resnet50",
                task="pressure-injury-stage-classification",
                artifact="models/pressure_injury_stage_classifier/pressure_injury_stage_resnet50.pth",
                status="specialist-candidate",
                framework=str(pressure_metadata.get("framework") or "PyTorch/torchvision"),
                version=str(pressure_metadata.get("version") or "pressure-injury-stage-heuristic-v1"),
                metrics=dict(pressure_metadata.get("validation_metrics") or {}),
                metadata_path="models/pressure_injury_stage_classifier/model_metadata.json",
                thresholds={"specialist_review": 0.82, "margin_review": 0.15},
                notes="Especialista LP-only para refinamento de estagio e explicabilidade.",
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

    def _get_pressure_classifier(self) -> PressureInjuryStageClassifier:
        if self._pressure_classifier_attempted:
            return self._pressure_classifier or PressureInjuryStageClassifier()

        self._pressure_classifier_attempted = True
        try:
            self._pressure_classifier = PressureInjuryStageClassifier()
        except Exception as exc:
            logger.warning(f"Falha ao inicializar classificador LP-only: {exc}")
            self._pressure_classifier = PressureInjuryStageClassifier()
        return self._pressure_classifier

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

    @staticmethod
    def _evaluation_etiology_hint(evaluation: dict[str, Any]) -> str:
        for key in ("wound_type", "etiology", "clinical_description"):
            if _looks_like_pressure_injury(evaluation.get(key)):
                return "pressure_injury"
        return ""

    def _fallback_output(self, evaluation: dict[str, Any]) -> dict[str, Any]:
        area = float(evaluation.get("wound_area_cm2") or 0.0)
        pain = float(evaluation.get("pain_score") or 0.0)
        hinted_etiology = self._evaluation_etiology_hint(evaluation)
        if hinted_etiology:
            etiology = hinted_etiology
        elif area >= 15:
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
                "etiology_hint": hinted_etiology or None,
                "registry": self.describe_registry(),
            },
        }

    def _specialize_pressure_injury(
        self,
        *,
        evaluation: dict[str, Any],
        image_path: Path,
        raw_output: dict[str, Any],
    ) -> tuple[dict[str, Any], str] | None:
        if not (
            _looks_like_pressure_injury(raw_output.get("etiology"))
            or _looks_like_pressure_injury(evaluation.get("wound_type"))
            or _looks_like_pressure_injury(evaluation.get("clinical_description"))
        ):
            return None

        image = cv2.imread(str(image_path))
        if image is None:
            return None

        classifier = self._get_pressure_classifier()
        prediction = classifier.predict(
            image,
            evaluation_context={
                "wound_area_cm2": float(evaluation.get("wound_area_cm2") or 0.0),
                "pain_score": float(evaluation.get("pain_score") or 0.0),
            },
        )
        merged = merge_pressure_injury_stage_assessment(raw_output, prediction)
        return merged, prediction.model_version

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
                "diagnostic_trace": {
                    "wound_type_considered": wound_type,
                    "confidence_considered": confidence,
                    "structured_context": {
                        "wound_area_cm2": float(evaluation.get("wound_area_cm2") or 0.0),
                        "pain_score": float(evaluation.get("pain_score") or 0.0),
                    },
                },
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
                    specialized = self._specialize_pressure_injury(
                        evaluation=evaluation,
                        image_path=image_path,
                        raw_output=raw_output,
                    )
                    model_version = descriptor.version or descriptor.id
                    if specialized is not None:
                        raw_output, model_version = specialized
                    return {
                        "raw_output": raw_output,
                        "model_version": model_version,
                        "model_descriptor": descriptor.to_dict(),
                    }

        fallback_output = self._fallback_output(evaluation)
        if image_record:
            image_path = Path(str(image_record.get("image_path") or ""))
            if image_path.exists():
                specialized = self._specialize_pressure_injury(
                    evaluation=evaluation,
                    image_path=image_path,
                    raw_output=fallback_output,
                )
                if specialized is not None:
                    fallback_output, model_version = specialized
                    return {
                        "raw_output": fallback_output,
                        "model_version": model_version,
                        "model_descriptor": descriptor.to_dict(),
                    }
        return {
            "raw_output": fallback_output,
            "model_version": DEFAULT_MODEL_VERSION,
            "model_descriptor": descriptor.to_dict(),
        }
