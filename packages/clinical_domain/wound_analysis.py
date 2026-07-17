"""Canonical HEAL+ wound-analysis application service and response contract."""

from __future__ import annotations

import base64
import hashlib
import io
import math
import time
from datetime import datetime, timezone
from typing import Any, Callable, Literal, Mapping

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from .validation import AnalyzeRoiPayload, ValidatedImage
from .workflow import AI_RESULT_CONTRACT_VERSION, build_headless_analyzer_result

WOUND_ANALYSIS_API_VERSION = "1.0.0"
WOUND_ANALYSIS_RESOURCE_TYPE = "wound_analysis"


class AnalyzerUnavailableError(RuntimeError):
    """Raised when the canonical clinical analyzer cannot be initialized."""


class _ContractModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class WoundAnalysisSubject(_ContractModel):
    patient_id: str | None = None
    evaluation_id: str | None = None


class WoundAnalysisExecution(_ContractModel):
    engine: str
    mode: Literal["model_assisted", "deterministic_fallback"]
    degraded: bool
    processing_time_ms: float = Field(ge=0)
    components: dict[str, str]
    warnings: list[str]


class WoundAnalysisSafety(_ContractModel):
    intended_use: str
    decision_support_only: bool = True
    clinician_review_required: bool = True
    regulatory_status: str
    limitations: list[str]


class WoundAnalysisTissue(_ContractModel):
    name: str
    name_en: str
    percentage: float = Field(ge=0, le=100)
    color_hex: str
    description: str = ""
    clinical_action: str = ""


class WoundAnalysisResultContract(_ContractModel):
    resource_type: Literal["wound_analysis"]
    api_version: str
    contract_version: str
    analysis_id: str = Field(min_length=1)
    status: Literal["completed"]
    generated_at: str
    model_version: str
    subject: WoundAnalysisSubject
    execution: WoundAnalysisExecution
    safety: WoundAnalysisSafety
    is_valid_wound: bool
    rejection_reason: str
    processing_time_ms: float = Field(ge=0)
    wound_area_px: int = Field(ge=0)
    tissues: list[WoundAnalysisTissue]
    inference: dict[str, Any]
    interpretation: dict[str, Any]
    metadata: dict[str, Any]
    links: dict[str, str]


def to_json_safe(value: Any) -> Any:
    """Convert analyzer and numpy values to strict JSON-compatible primitives."""

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_json_safe(item) for item in value]

    item = getattr(value, "item", None)
    if callable(item):
        try:
            return to_json_safe(item())
        except Exception:
            pass
    if hasattr(value, "tolist"):
        try:
            return to_json_safe(value.tolist())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        return to_json_safe(vars(value))
    return str(value)


def build_wound_analysis_request_hash(
    image: ValidatedImage,
    *,
    patient_id: str | None,
    evaluation_id: str | None,
    roi_payloads: list[AnalyzeRoiPayload],
) -> str:
    """Build a deterministic hash used to enforce safe idempotent retries."""

    digest = hashlib.sha256()
    digest.update(image.content)
    digest.update((patient_id or "").encode("utf-8"))
    digest.update((evaluation_id or "").encode("utf-8"))
    for roi in roi_payloads:
        digest.update(roi.model_dump_json(exclude_none=True).encode("utf-8"))
    return digest.hexdigest()


def _encode_visual_payload(
    image_array: Any,
    *,
    label: str,
    description: str,
    mime_type: str = "image/jpeg",
) -> dict[str, Any] | None:
    if image_array is None:
        return None

    import cv2
    import numpy as np

    image = np.asarray(image_array)
    if image.size == 0:
        return None
    if image.dtype != np.uint8:
        image = np.clip(image, 0, 255).astype(np.uint8)
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    height, width = image.shape[:2]
    max_edge = max(height, width)
    if max_edge > 1400:
        scale = 1400.0 / float(max_edge)
        image = cv2.resize(
            image,
            (max(1, int(width * scale)), max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )

    if mime_type == "image/png":
        success, buffer = cv2.imencode(".png", image)
    else:
        success, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        mime_type = "image/jpeg"
    if not success:
        return None

    encoded = base64.b64encode(buffer.tobytes()).decode("ascii")
    return {
        "label": label,
        "description": description,
        "mime_type": mime_type,
        "data_url": f"data:{mime_type};base64,{encoded}",
    }


def _execution_metadata(report: Any, result: Mapping[str, Any], elapsed_ms: float) -> dict[str, Any]:
    inference = result.get("inference") if isinstance(result.get("inference"), Mapping) else {}
    has_learned_model = bool(
        getattr(report, "resnet_prediction", None)
        or getattr(report, "dl_prediction", None)
        or getattr(report, "ensemble_classification", None)
    )
    fallback_used = bool((inference or {}).get("fallback_used")) or not has_learned_model
    warnings = ["O resultado exige revisão clínica e não substitui diagnóstico profissional."]
    if fallback_used:
        warnings.append("Modelo aprendido indisponível ou inconclusivo; heurísticas determinísticas foram utilizadas.")

    return {
        "engine": "heal-clinical-wound-analyzer",
        "mode": "deterministic_fallback" if fallback_used else "model_assisted",
        "degraded": fallback_used,
        "processing_time_ms": round(max(0.0, elapsed_ms), 2),
        "components": {
            "wound_validation": "ready",
            "roi": "manual" if result.get("roi") or result.get("rois") else "automatic",
            "tissue_segmentation": "ready",
            "learned_classifier": "ready" if has_learned_model else "unavailable",
        },
        "warnings": warnings,
    }


def wound_analysis_capabilities(*, analyzer_available: bool) -> dict[str, Any]:
    """Describe runtime behavior and clinical limitations for API consumers."""

    return {
        "service": "HEAL+ Wound Analysis API",
        "resource": WOUND_ANALYSIS_RESOURCE_TYPE,
        "api_version": WOUND_ANALYSIS_API_VERSION,
        "contract_version": AI_RESULT_CONTRACT_VERSION,
        "runtime": {
            "status": "ready" if analyzer_available else "unavailable",
            "canonical_engine": "heal-clinical-wound-analyzer",
            "generative_fallback_allowed": False,
        },
        "inputs": {
            "content_type": "multipart/form-data",
            "image_field": "image",
            "image_formats": ["image/jpeg", "image/png", "image/webp"],
            "optional_fields": ["patient_id", "evaluation_id", "roi_payload"],
            "roi_tools": ["polygon", "freehand", "circle"],
            "multiple_rois": True,
        },
        "outputs": {
            "tissue_taxonomy": ["granulation", "slough", "necrosis", "epithelial"],
            "visuals": ["detection", "segmentation", "combined", "attention"],
            "retrievable": True,
            "idempotency_key_supported": True,
        },
        "clinical_use": {
            "classification": "clinical_decision_support_research",
            "clinician_review_required": True,
            "limitations_disclosed_per_result": True,
        },
        "evidence_basis": [
            {
                "title": "Wound tissue classification using color and texture features",
                "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC4121018/",
                "scope": "methodological_reference",
            },
            {
                "title": "AI-assisted wound tissue color calibration study",
                "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC9858639/",
                "scope": "methodological_reference",
            },
        ],
    }


class WoundAnalysisService:
    """Run the canonical analyzer and produce a validated, auditable resource."""

    def __init__(self, analyzer_provider: Callable[[], Any | None]):
        self._analyzer_provider = analyzer_provider

    def analyze(
        self,
        image: ValidatedImage,
        *,
        analysis_id: str,
        patient_id: str | None,
        evaluation_id: str | None,
        manual_roi_mask: Any = None,
        manual_roi_masks: list[Any] | None = None,
        roi_metadata: dict[str, Any] | None = None,
        roi_metadata_list: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        analyzer = self._analyzer_provider()
        if analyzer is None:
            raise AnalyzerUnavailableError("canonical clinical analyzer is unavailable")

        import cv2
        import numpy as np

        started_at = time.perf_counter()
        decoded = Image.open(io.BytesIO(image.content)).convert("RGB")
        image_bgr = cv2.cvtColor(np.array(decoded), cv2.COLOR_RGB2BGR)
        report = analyzer.analyze(
            image_bgr,
            manual_roi_mask=manual_roi_mask,
            manual_roi_masks=manual_roi_masks or [],
            roi_metadata=roi_metadata,
            roi_metadata_list=roi_metadata_list or [],
        )
        generated_at = datetime.now(timezone.utc).isoformat()
        result = build_headless_analyzer_result(
            report,
            analysis_id=analysis_id,
            patient_id=patient_id or "",
            image_filename=image.original_name or "unknown",
            image_content_type=image.mime_type,
            generated_at=generated_at,
        )
        result["evaluation_id"] = evaluation_id or ""
        if roi_metadata and not result.get("roi"):
            result["roi"] = roi_metadata
        if roi_metadata_list and not result.get("rois"):
            result["rois"] = roi_metadata_list

        roi_count = len(roi_metadata_list or [])
        detection_label = "Região analisada"
        detection_description = "Contorno e área considerada pelo motor clínico."
        if roi_count > 1:
            detection_label = f"{roi_count} ROIs manuais confirmadas"
            detection_description = "ROIs manuais confirmadas e unidas como filtro principal da análise."
        elif roi_metadata:
            detection_label = "ROI manual confirmada"
            detection_description = "Delimitação manual aplicada como filtro principal da análise."

        result["visuals"] = {
            "detection": _encode_visual_payload(
                getattr(report, "detection_overlay", None),
                label=detection_label,
                description=detection_description,
            ),
            "segmentation": _encode_visual_payload(
                getattr(report, "segmentation_map", None),
                label="Mapa de tecidos",
                description="Distribuição segmentada; azul-ardósia representa região interna incerta.",
                mime_type="image/png",
            ),
            "combined": _encode_visual_payload(
                getattr(report, "tissue_overlay", None),
                label="Visualização combinada",
                description="Imagem original combinada com a leitura do motor clínico.",
            ),
            "attention": _encode_visual_payload(
                getattr(report, "grad_cam_overlay", None),
                label="Mapa de atenção",
                description="Regiões de maior relevância quando o classificador aprendido está disponível.",
            ),
        }

        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        result.update(
            {
                "resource_type": WOUND_ANALYSIS_RESOURCE_TYPE,
                "api_version": WOUND_ANALYSIS_API_VERSION,
                "status": "completed",
                "subject": {"patient_id": patient_id, "evaluation_id": evaluation_id},
                "execution": _execution_metadata(report, result, elapsed_ms),
                "safety": {
                    "intended_use": "Apoio à avaliação visual de feridas por profissional habilitado.",
                    "decision_support_only": True,
                    "clinician_review_required": True,
                    "regulatory_status": "not_declared",
                    "limitations": [
                        "A qualidade, iluminação, escala e enquadramento da imagem alteram o resultado.",
                        "Percentuais sem escala física não representam área em cm².",
                        "Etiologia e conduta não podem ser confirmadas apenas por fotografia.",
                    ],
                },
                "links": {
                    "self": f"/api/v1/wound-analyses/{analysis_id}",
                    "capabilities": "/api/v1/wound-analyses/capabilities",
                },
            }
        )
        result.setdefault("metadata", {}).update(
            {
                "image_sha256": hashlib.sha256(image.content).hexdigest(),
                "image_width": image.width,
                "image_height": image.height,
                "roi_count": roi_count,
            }
        )

        safe_result = to_json_safe(result)
        return WoundAnalysisResultContract.model_validate(safe_result).model_dump(mode="json")
