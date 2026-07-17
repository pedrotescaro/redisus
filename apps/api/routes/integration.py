# -*- coding: utf-8 -*-
"""Integration routes consolidated from the legacy backend app."""

from __future__ import annotations

import io
import json
import math
import os
import re
import subprocess
import tempfile
import traceback
import uuid
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from flask import Blueprint, abort, current_app, g, jsonify, request, send_file
from PIL import Image

from packages.clinical_domain.wound_analysis import (
    AnalyzerUnavailableError,
    WoundAnalysisService,
    build_wound_analysis_request_hash,
    wound_analysis_capabilities,
)
from packages.clinical_domain.workflow import build_headless_analyzer_result
from packages.clinical_domain.validation import (
    AIChatPayload,
    AnalyzeRoiPayload,
    assert_allowed_form_fields,
    validate_and_sanitize_image_upload,
    validate_roi_form_value,
    validate_json_request,
)
from packages.shared.runtime import load_project_env
from packages.shared.security import (
    current_user,
    current_user_required,
    enforce_rate_limit,
    ensure_evaluation_access,
    ensure_patient_access,
    filter_patients_for_user,
    is_admin,
    user_display_name,
    user_uid,
)

load_project_env()

from backend.firebase_admin_setup import get_firestore_db, get_storage_bucket, is_firebase_ready  # noqa: E402

import threading

integration_api = Blueprint("integration_api", __name__, url_prefix="/api/v1")

_gemini_model = None
_wound_analyzer = None
_MOJIBAKE_MARKERS = ("\u00c3", "\u00c2", "\u00e2\u20ac", "\ufffd")
_gemini_lock = threading.Lock()
_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_GEMINI_SYSTEM_INSTRUCTION = (
    "Voce e o assistente de IA HEAL+ da plataforma REDISUS. "
    "Especialista em estomaterapia, analise de feridas, cicatrizacao "
    "e cuidados clinicos com feridas cronicas. "
    "Responda em portugues brasileiro, de forma tecnica mas acessivel. "
    "Seja conciso e direto nas respostas."
)

try:
    import numpy as _np
except Exception:  # pragma: no cover - numpy is expected in runtime but keep route resilient
    _np = None


def _score_chat_response(text: str) -> float:
    if not text:
        return -1.0
    text = text.strip()
    if len(text) < 10:
        return 0.0
    
    score = 1.0
    if "\n-" in text or "\n*" in text:
        score += 2.0
    if "###" in text or "##" in text:
        score += 1.5
    if "**" in text:
        score += 1.0
    length_bonus = min(len(text) / 500.0, 1.5)
    score += length_bonus
    return score


def _score_labels_response(text: str) -> float:
    if not text:
        return -1.0
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "labels" in data and isinstance(data["labels"], list):
            num_labels = len(data["labels"])
            if num_labels == 0:
                return 1.0
            
            confidences = [
                float(item.get("confidence", 0.5)) 
                for item in data["labels"] 
                if isinstance(item, dict)
            ]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
            return 10.0 + float(num_labels) * 0.5 + avg_conf
    except Exception:
        pass
    return 0.0


def _get_active_keys() -> list[str]:
    keys = []
    for i in range(1, 6):
        key_val = os.getenv(f"GEMINI_API_KEY_{i}")
        if key_val:
            keys.append(key_val.strip())
    if not keys:
        default_key = os.getenv("GOOGLE_AI_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
        if default_key:
            keys.append(default_key.strip())
    return keys


def _call_gemini_with_key(api_key: str, prompt: Any, system_instruction: str) -> Optional[str]:
    try:
        with _gemini_lock:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=system_instruction,
            )
            response = model.generate_content(prompt)
            return response.text
    except Exception as e:
        import logging
        logging.error(f"Error calling Gemini with key {api_key[:8]}...: {e}")
        return None


def _call_gemini_vision(image_bytes: bytes, prompt: str) -> Optional[str]:
    keys = _get_active_keys()
    if not keys:
        return None
    
    import io
    from PIL import Image
    try:
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        import logging
        logging.error(f"Error loading image for Gemini Vision: {e}")
        return None

    for key in keys:
        try:
            with _gemini_lock:
                import google.generativeai as genai
                genai.configure(api_key=key)
                model = genai.GenerativeModel(model_name="gemini-2.5-flash")
                response = model.generate_content([prompt, pil_image])
                if response and response.text:
                    return response.text
        except Exception as e:
            import logging
            logging.error(f"Error calling Gemini Vision with key {key[:8]}...: {e}")
            continue
    return None


def _generate_best_response(prompt: Any, system_instruction: str, is_json: bool = False) -> Optional[str]:
    keys = _get_active_keys()
    if not keys:
        return None
    
    responses = []
    for key in keys:
        text = _call_gemini_with_key(key, prompt, system_instruction)
        if text:
            responses.append(text)
            
    if not responses:
        return None
        
    if len(responses) == 1:
        return responses[0]
        
    if is_json:
        scored = [(text, _score_labels_response(text)) for text in responses]
    else:
        scored = [(text, _score_chat_response(text)) for text in responses]
        
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0]


def _init_gemini():
    global _gemini_model
    if _gemini_model is not None:
        return _gemini_model

    keys = _get_active_keys()
    if not keys:
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=keys[0])
        _gemini_model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=_GEMINI_SYSTEM_INSTRUCTION,
        )
        return _gemini_model
    except Exception:
        return None


def _get_wound_analyzer():
    global _wound_analyzer
    if _wound_analyzer is not None:
        return _wound_analyzer
    try:
        from src.processing.clinical_wound_analyzer_core import ClinicalWoundAnalyzer

        _wound_analyzer = ClinicalWoundAnalyzer()
        return _wound_analyzer
    except Exception:
        return None


def get_integration_service_status() -> Dict[str, Any]:
    model = _init_gemini()
    return {
        "official_api": "ready",
        "gemini": "ready" if model is not None else "unconfigured",
        "wound_analyzer": "ready" if _wound_analyzer is not None else "not_loaded",
        "firebase_admin": "configured" if is_firebase_ready() else "unavailable",
    }


def get_current_user() -> Optional[Dict[str, Any]]:
    return current_user()


def _repair_mojibake_text(value: str) -> str:
    if not value or not any(marker in value for marker in _MOJIBAKE_MARKERS):
        return value

    for encoding in ("latin1", "cp1252"):
        try:
            repaired = value.encode(encoding).decode("utf-8")
        except UnicodeError:
            continue
        if repaired:
            return repaired
    return value


def _to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value

    if isinstance(value, str):
        return _repair_mojibake_text(value)

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, Mapping):
        return {str(key): _to_json_safe(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_to_json_safe(item) for item in value]

    if _np is not None:
        if isinstance(value, _np.generic):
            return _to_json_safe(value.item())
        if isinstance(value, _np.ndarray):
            return _to_json_safe(value.tolist())

    item = getattr(value, "item", None)
    if callable(item):
        try:
            return _to_json_safe(item())
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        return _to_json_safe(vars(value))

    return str(value)


def _rule_based_response(message: str) -> str:
    msg = message.lower()
    if any(w in msg for w in ["ferida", "ulcera", "lesao", "wound"]):
        return (
            "Para analise de feridas, recomendo fazer upload de uma foto na secao "
            "de avaliacoes. O sistema HEAL+ utiliza IA para classificar tecido, "
            "acompanhar cicatrizacao e sugerir condutas clinicas.\n\n"
            "Posso ajudar com:\n"
            "- Classificacao tecidual\n"
            "- Escalas clinicas (PUSH, BWAT, Braden)\n"
            "- Recomendacoes de curativo\n"
            "- Monitoramento de evolucao"
        )
    if any(w in msg for w in ["relatorio", "report", "pdf", "exportar"]):
        return (
            "Para gerar relatorios, use a secao de relat\u00f3rios da plataforma. "
            "O fluxo atual suporta relatorios estruturados e exportacao."
        )
    if any(w in msg for w in ["ola", "oi", "bom dia", "boa tarde", "boa noite", "hello"]):
        return (
            "Ola! Sou o assistente de IA do HEAL+ / REDISUS. "
            "Posso ajudar com analise de imagens, relatorios clinicos e duvidas sobre o sistema."
        )
    return (
        "Posso ajudar com analise de feridas, busca de dados clinicos, relatorios "
        "e duvidas sobre o modulo de diagnostico. Reformule a pergunta se precisar."
    )


def _serialize_roi_payloads(payloads: list[AnalyzeRoiPayload]) -> list[dict[str, Any]]:
    serialized_payloads: list[dict[str, Any]] = []
    for index, payload in enumerate(payloads, start=1):
        serialized = payload.model_dump(mode="python")
        serialized["source"] = "manual"
        serialized["confirmed"] = True
        serialized["selection_index"] = index
        serialized_payloads.append(serialized)
    return serialized_payloads


def _build_manual_roi_mask(
    payload: AnalyzeRoiPayload | None,
    *,
    width: int,
    height: int,
):
    if payload is None:
        return None

    import cv2
    import numpy as np

    mask = np.zeros((height, width), dtype=np.uint8)
    max_x = max(width - 1, 0)
    max_y = max(height - 1, 0)
    polygon = np.array(
        [
            [
                int(round(min(max(point.x, 0.0), 1.0) * max_x)),
                int(round(min(max(point.y, 0.0), 1.0) * max_y)),
            ]
            for point in payload.points
        ],
        dtype=np.int32,
    )

    if polygon.shape[0] < 3:
        return None

    cv2.fillPoly(mask, [polygon], 255)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    return mask


def _build_manual_roi_masks(
    payloads: list[AnalyzeRoiPayload],
    *,
    width: int,
    height: int,
):
    masks = []
    for payload in payloads:
        mask = _build_manual_roi_mask(payload, width=width, height=height)
        if mask is not None:
            masks.append(mask)
    return masks


def _combine_manual_roi_masks(masks):
    if not masks:
        return None

    import cv2
    import numpy as np

    combined = np.zeros_like(masks[0], dtype=np.uint8)
    for mask in masks:
        combined = cv2.bitwise_or(combined, mask)
    return combined if np.any(combined > 0) else None


def _mask_to_png_bytes(mask) -> bytes:
    import cv2
    import numpy as np

    mask_image = np.asarray(mask)
    if mask_image.dtype != np.uint8:
        mask_image = np.clip(mask_image, 0, 255).astype(np.uint8)

    success, buffer = cv2.imencode(".png", mask_image)
    if not success:
        return b""
    return buffer.tobytes()


def _problem_response(
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    errors: list[dict[str, Any]] | None = None,
):
    """Return RFC 9457-compatible errors while preserving the legacy error code."""

    request_id = getattr(g, "redisus_request_id", None) or request.headers.get("X-Request-ID") or str(uuid.uuid4())
    payload: dict[str, Any] = {
        "type": f"https://heal-plus.local/problems/{code}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.path,
        "code": code,
        "error": code,
        "request_id": request_id,
    }
    if errors:
        payload["errors"] = errors
    response = jsonify(payload)
    response.status_code = status
    response.content_type = "application/problem+json"
    return response


def _validated_idempotency_key() -> str | None:
    key = (request.headers.get("Idempotency-Key") or "").strip()
    if not key:
        return None
    if not _IDEMPOTENCY_KEY_PATTERN.fullmatch(key):
        abort(400, description="Idempotency-Key must contain 8 to 128 safe characters")
    return key


def _validate_roi_image_context(
    roi_payloads: list[AnalyzeRoiPayload],
    *,
    width: int,
    height: int,
) -> None:
    for index, roi in enumerate(roi_payloads):
        if not roi.confirmed:
            abort(422, description=f"roi_payload[{index}] must be confirmed before analysis")
        if roi.image_width != width or roi.image_height != height:
            abort(
                422,
                description=(
                    f"roi_payload[{index}] image dimensions do not match the uploaded image "
                    f"({width}x{height})"
                ),
            )


@integration_api.route("/wound-analyses/capabilities", methods=["GET"])
def get_wound_analysis_capabilities():
    current_user_required()
    enforce_rate_limit("wound_analysis_read", 120)
    return jsonify(wound_analysis_capabilities(analyzer_available=_get_wound_analyzer() is not None))


@integration_api.route("/wound-analyses", methods=["POST"])
def create_wound_analysis():
    user = current_user_required()
    enforce_rate_limit("wound_analysis", 20)
    if "image" not in request.files:
        return _problem_response(
            status=400,
            code="missing_image",
            title="Imagem obrigatória",
            detail="Envie a imagem clínica no campo multipart 'image'.",
        )
    unexpected_files = sorted(set(request.files.keys()) - {"image"})
    if unexpected_files:
        abort(400, description=f"unexpected file fields: {', '.join(unexpected_files)}")

    assert_allowed_form_fields(request.form, allowed={"patient_id", "evaluation_id", "roi_payload"})
    patient_id = (request.form.get("patient_id") or "").strip() or None
    evaluation_id = (request.form.get("evaluation_id") or "").strip() or None
    if patient_id and len(patient_id) > 80:
        abort(400, description="patient_id exceeds maximum length")
    if evaluation_id and len(evaluation_id) > 80:
        abort(400, description="evaluation_id exceeds maximum length")

    database = current_app.extensions.get("redisus_db")
    if database is None:
        return _problem_response(
            status=503,
            code="persistence_unavailable",
            title="Persistência indisponível",
            detail="O armazenamento oficial de análises não está disponível.",
        )

    if evaluation_id:
        evaluation = ensure_evaluation_access(database, evaluation_id, user=user)
        evaluation_patient_id = str(evaluation.get("patient_id") or "")
        if patient_id and patient_id != evaluation_patient_id:
            return _problem_response(
                status=409,
                code="clinical_context_conflict",
                title="Contexto clínico conflitante",
                detail="patient_id não corresponde ao paciente da evaluation_id informada.",
            )
        patient_id = evaluation_patient_id
    elif patient_id:
        patient = ensure_patient_access(database, patient_id, user=user)
        patient_id = str(patient.id)

    roi_payloads = validate_roi_form_value(request.form.get("roi_payload"), field_name="roi_payload")
    validated_image = validate_and_sanitize_image_upload(request.files["image"])
    _validate_roi_image_context(
        roi_payloads,
        width=validated_image.width,
        height=validated_image.height,
    )
    idempotency_key = _validated_idempotency_key()
    owner_uid = user_uid(user) or "unknown"
    request_hash = build_wound_analysis_request_hash(
        validated_image,
        patient_id=patient_id,
        evaluation_id=evaluation_id,
        roi_payloads=roi_payloads,
    )

    if idempotency_key:
        previous = database.get_wound_analysis_by_idempotency_key(
            owner_uid=owner_uid,
            idempotency_key=idempotency_key,
        )
        if previous:
            if previous.get("request_hash") != request_hash:
                return _problem_response(
                    status=409,
                    code="idempotency_conflict",
                    title="Chave de idempotência reutilizada",
                    detail="A mesma Idempotency-Key já foi usada com outra imagem ou contexto clínico.",
                )
            response = jsonify(previous.get("payload") or {})
            response.headers["X-Idempotent-Replay"] = "true"
            response.headers["Location"] = f"/api/v1/wound-analyses/{previous['id']}"
            return response

    manual_roi_masks = _build_manual_roi_masks(
        roi_payloads,
        width=validated_image.width,
        height=validated_image.height,
    )
    manual_roi_mask = _combine_manual_roi_masks(manual_roi_masks)
    manual_roi_metadata_list = _serialize_roi_payloads(roi_payloads)
    manual_roi_summary = None
    if len(manual_roi_metadata_list) == 1:
        manual_roi_summary = dict(manual_roi_metadata_list[0])
    elif manual_roi_metadata_list:
        manual_roi_summary = {
            "confirmed": True,
            "selection_count": len(manual_roi_metadata_list),
            "source": "manual",
            "tools": [item.get("tool") for item in manual_roi_metadata_list if item.get("tool")],
            "version": str(manual_roi_metadata_list[0].get("version") or ""),
        }

    analysis_id = str(uuid.uuid4())
    service = WoundAnalysisService(_get_wound_analyzer)
    try:
        result = service.analyze(
            validated_image,
            analysis_id=analysis_id,
            patient_id=patient_id,
            evaluation_id=evaluation_id,
            manual_roi_mask=manual_roi_mask,
            manual_roi_masks=manual_roi_masks,
            roi_metadata=manual_roi_summary,
            roi_metadata_list=manual_roi_metadata_list,
        )
    except AnalyzerUnavailableError:
        return _problem_response(
            status=503,
            code="analyzer_unavailable",
            title="Motor clínico indisponível",
            detail="O motor canônico do HEAL+ não pôde ser inicializado. Tente novamente mais tarde.",
        )

    result["persistence"] = {"stored": True, "backend": "sqlite"}
    saved = database.save_wound_analysis_result(
        analysis_id=analysis_id,
        owner_uid=owner_uid,
        patient_id=patient_id,
        evaluation_id=evaluation_id,
        request_hash=request_hash,
        idempotency_key=idempotency_key,
        payload=result,
    )
    if not saved:
        if idempotency_key:
            replay = database.get_wound_analysis_by_idempotency_key(
                owner_uid=owner_uid,
                idempotency_key=idempotency_key,
            )
            if replay and replay.get("request_hash") == request_hash:
                response = jsonify(replay.get("payload") or {})
                response.headers["X-Idempotent-Replay"] = "true"
                response.headers["Location"] = f"/api/v1/wound-analyses/{replay['id']}"
                return response
        return _problem_response(
            status=503,
            code="persistence_unavailable",
            title="Persistência indisponível",
            detail="A análise foi interrompida porque o resultado não pôde ser persistido com segurança.",
        )

    response = jsonify(result)
    response.status_code = 201
    response.headers["Location"] = f"/api/v1/wound-analyses/{analysis_id}"
    return response


@integration_api.route("/wound-analyses/<analysis_id>", methods=["GET"])
def get_wound_analysis(analysis_id: str):
    user = current_user_required()
    enforce_rate_limit("wound_analysis_read", 120)
    database = current_app.extensions.get("redisus_db")
    record = database.get_wound_analysis_result(analysis_id) if database is not None else None
    if not record:
        abort(404, description="wound analysis not found")

    patient_id = str(record.get("patient_id") or "")
    if patient_id:
        ensure_patient_access(database, patient_id, user=user)
    elif not is_admin(user) and str(record.get("owner_uid") or "") != str(user_uid(user) or ""):
        abort(403, description="wound analysis access denied")
    return jsonify(record.get("payload") or {})


def _find_latex_image_sources(latex_code: str, *, max_images: int = 12) -> list[tuple[int, int, str]]:
    """Locate includegraphics sources with a bounded linear scanner."""

    marker = "\\includegraphics"
    cursor = 0
    sources: list[tuple[int, int, str]] = []
    text_length = len(latex_code)
    while cursor < text_length and len(sources) < max_images:
        marker_start = latex_code.find(marker, cursor)
        if marker_start < 0:
            break
        position = marker_start + len(marker)
        while position < text_length and latex_code[position].isspace():
            position += 1
        if position < text_length and latex_code[position] == "[":
            option_end = latex_code.find("]", position + 1)
            if option_end < 0 or option_end - position > 512:
                raise ValueError("invalid includegraphics options")
            position = option_end + 1
        while position < text_length and latex_code[position].isspace():
            position += 1
        if position >= text_length or latex_code[position] != "{":
            cursor = marker_start + len(marker)
            continue
        source_start = position + 1
        source_end = latex_code.find("}", source_start)
        if source_end < 0:
            raise ValueError("unterminated includegraphics source")
        source = latex_code[source_start:source_end].strip()
        sources.append((source_start, source_end, source))
        cursor = source_end + 1
    if latex_code.find(marker, cursor) >= 0:
        raise ValueError("too many embedded images")
    return sources


def _prepare_latex_images(latex_code: str, directory: Path) -> str:
    """Materialize bounded image data URLs without network or user-controlled paths."""

    allowed_media = {
        "data:image/png;base64": ".png",
        "data:image/jpeg;base64": ".jpg",
        "data:image/jpg;base64": ".jpg",
    }
    replacements: list[tuple[int, int, str]] = []
    for index, (source_start, source_end, source) in enumerate(_find_latex_image_sources(latex_code)):
        metadata, separator, encoded = source.partition(",")
        normalized_metadata = metadata.lower()
        if not separator or normalized_metadata not in allowed_media:
            raise ValueError("includegraphics accepts only embedded PNG or JPEG data URLs")
        compact_encoded = "".join(encoded.split())
        if len(compact_encoded) > 8_000_000:
            raise ValueError("embedded image exceeds maximum size")
        try:
            image_bytes = base64.b64decode(compact_encoded, validate=True)
        except ValueError as exc:
            raise ValueError("invalid embedded image encoding") from exc
        if not image_bytes or len(image_bytes) > 6_000_000:
            raise ValueError("embedded image exceeds maximum size")
        extension = allowed_media[normalized_metadata]
        filename = f"embedded_{index}{extension}"
        (directory / filename).write_bytes(image_bytes)
        replacements.append((source_start, source_end, filename))

    for source_start, source_end, filename in reversed(replacements):
        latex_code = latex_code[:source_start] + filename + latex_code[source_end:]
    return latex_code


def _validate_latex_commands(latex_code: str) -> None:
    normalized = latex_code.casefold()
    forbidden_commands = (
        "\\write18",
        "\\input",
        "\\include{",
        "\\openin",
        "\\openout",
        "\\read",
        "\\write",
        "\\immediate",
        "\\catcode",
        "\\csname",
        "\\newread",
        "\\newwrite",
    )
    if any(command in normalized for command in forbidden_commands):
        raise ValueError("latex source contains a forbidden command")


@integration_api.route("/analyze", methods=["POST"])
def analyze_image():
    user = current_user_required()
    enforce_rate_limit("analyze", 20)
    if "image" not in request.files:
        return jsonify({"error": "missing_image", "detail": "Campo 'image' obrigatorio"}), 400

    image_file = request.files["image"]
    assert_allowed_form_fields(request.form, allowed={"patient_id", "roi_payload"})
    patient_id = (request.form.get("patient_id") or "").strip()
    roi_payloads = validate_roi_form_value(
        request.form.get("roi_payload"),
        field_name="roi_payload",
    )

    try:
        import cv2
        import numpy as np

        def encode_visual_payload(
            image_array,
            *,
            label: str,
            description: str,
            mime_type: str = "image/jpeg",
        ) -> Optional[dict[str, Any]]:
            if image_array is None:
                return None

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
                success, buffer = cv2.imencode(
                    ".jpg",
                    image,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 88],
                )
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

        validated_image = validate_and_sanitize_image_upload(image_file)
        image = cv2.cvtColor(np.array(Image.open(io.BytesIO(validated_image.content)).convert("RGB")), cv2.COLOR_RGB2BGR)
        manual_roi_masks = _build_manual_roi_masks(
            roi_payloads,
            width=validated_image.width,
            height=validated_image.height,
        )
        manual_roi_mask = _combine_manual_roi_masks(manual_roi_masks)
        manual_roi_metadata_list = _serialize_roi_payloads(roi_payloads)
        manual_roi_summary = None
        if manual_roi_metadata_list:
            if len(manual_roi_metadata_list) == 1:
                manual_roi_summary = dict(manual_roi_metadata_list[0])
            else:
                manual_roi_summary = {
                    "confirmed": True,
                    "selection_count": len(manual_roi_metadata_list),
                    "source": "manual",
                    "tools": [
                        str(item.get("tool"))
                        for item in manual_roi_metadata_list
                        if item.get("tool")
                    ],
                    "version": str(manual_roi_metadata_list[0].get("version") or ""),
                }

        analyzer = _get_wound_analyzer()
        if analyzer is None:
            vision_prompt = """Você é um clínico especialista em estomaterapia e cicatrização de feridas crônicas.
Analise a imagem da ferida fornecida e retorne um objeto JSON puríssimo que siga estritamente o esquema abaixo.

Regras Clínicas de Análise:
1. O campo "is_valid_wound" deve ser true se a imagem for de fato uma ferida/lesão cutânea humana. Se não for, defina como false e preencha "rejection_reason".
2. Classifique os tecidos presentes na ferida ("tissues") em quatro categorias possíveis:
   - "Necrose" (name_en: "necrosis", color_hex: "#18181b")
   - "Esfacelo" (name_en: "slough_fibrin", color_hex: "#eab308")
   - "Granulação" (name_en: "granulation", color_hex: "#dc2626")
   - "Epitelização" (name_en: "epithelial", color_hex: "#10b981")
   A soma das porcentagens dos tecidos deve ser exatamente 100%.
3. Avalie as bordas da ferida ("border_analysis"): presença de maceração, inflamação, se são regulares ou não, e descreva-as.
4. Identifique a provável etiologia ("inference"):
   - "venosa" (Úlcera Venosa)
   - "pressao" (Lesão por Pressão)
   - "diabetica" (Pé Diabético)
   - "arterial" (Úlcera Arterial)
   - "cirurgica" (Ferida Cirúrgica)
   - "traumatica" (Ferida Traumática)
   Forneça a confiança estimada de 0.0 a 1.0.
5. Indique as recomendações de tratamento e cuidados no campo "interpretation".

Esquema JSON a retornar:
{
  "analysis_id": "UUID_DA_ANALISE",
  "contract_version": "2.0",
  "model_version": "gemini-2.0-flash-vision",
  "generated_at": "ISO_TIMESTAMP_ATUAL",
  "primary_tissue": "necrosis" | "slough_fibrin" | "granulation" | "epithelial",
  "primary_justification": "Justificativa clínica para o tecido primário",
  "processing_time_ms": 250,
  "is_valid_wound": true,
  "rejection_reason": "",
  "health_score": 75,
  "wound_area_px": 8000,
  "tissues": [
    {
      "name": "Granulação",
      "name_en": "granulation",
      "percentage": 60,
      "color_hex": "#dc2626",
      "description": "Tecido vermelho e saudável de cicatrização",
      "clinical_action": "Manter umidade adequada"
    }
  ],
  "border_analysis": {
    "maceration": false,
    "inflammation": true,
    "regular_borders": true,
    "description": "Bordas bem definidas com leve eritema perilesional"
  },
  "metadata": {},
  "inference": {
    "colors": {},
    "tissue_percentages": {
      "granulation": 60,
      "slough_fibrin": 30,
      "necrosis": 10,
      "epithelial": 0
    },
    "etiology": "venosa",
    "etiology_label": "Úlcera Venosa",
    "confidence": 0.9,
    "wound_area_cm2": 15.4,
    "fallback_used": false,
    "needs_expert_review": false,
    "confidence_level": "high",
    "confidence_entropy": 0.15,
    "confidence_margin": 0.75
  },
  "interpretation": {
    "summary": "Ferida em fase de granulação predominante com presença de esfacelo leve.",
    "risk_level": "medium",
    "priority": "normal",
    "follow_up_days": 7,
    "requires_expert_review": false,
    "recommendations": [
      "Realizar limpeza com jato de soro fisiológico ou PHMB",
      "Aplicar cobertura de hidrogel ou alginato de cálcio nas áreas de esfacelo"
    ]
  }
}

Importante: Responda APENAS com o JSON válido. Não inclua delimitadores markdown como ```json ... ```, nem cabeçalhos, introduções ou explicações.
"""
            vision_prompt = vision_prompt.replace("UUID_DA_ANALISE", str(uuid.uuid4()))
            vision_prompt = vision_prompt.replace("ISO_TIMESTAMP_ATUAL", datetime.now(timezone.utc).isoformat())

            gemini_response = _call_gemini_vision(validated_image.content, vision_prompt)
            if not gemini_response:
                return jsonify({"error": "analyzer_unavailable", "detail": "Modelo local indisponivel e falha ao chamar Gemini Vision"}), 503
            
            try:
                clean_text = gemini_response.strip()
                if clean_text.startswith("```"):
                    if clean_text.startswith("```json"):
                        clean_text = clean_text[7:]
                    else:
                        clean_text = clean_text[3:]
                    if clean_text.endswith("```"):
                        clean_text = clean_text[:-3]
                    clean_text = clean_text.strip()
                
                analysis_result = json.loads(clean_text)
                
                encoded_image = base64.b64encode(validated_image.content).decode("ascii")
                analysis_result["visuals"] = {
                    "detection": None,
                    "segmentation": None,
                    "combined": {
                        "label": "Foto da ferida",
                        "description": "Foto original da lesao enviada para analise.",
                        "mime_type": validated_image.mime_type,
                        "data_url": f"data:{validated_image.mime_type};base64,{encoded_image}",
                    },
                    "attention": None
                }
                
                if manual_roi_summary:
                    analysis_result["roi"] = manual_roi_summary
                if manual_roi_metadata_list:
                    analysis_result["rois"] = manual_roi_metadata_list
                    
                return jsonify(analysis_result)
            except Exception as e:
                import logging
                logging.error(f"Error parsing Gemini Vision response: {e}. Raw response: {gemini_response}")
                return jsonify({"error": "gemini_parse_failed", "detail": f"Erro ao processar resposta do Gemini: {str(e)}"}), 502

        analysis_id = str(uuid.uuid4())
        owner_uid = user_uid(user)
        linked_patient_id = None
        if patient_id:
            database = current_app.extensions.get("redisus_db")
            if database is None:
                return jsonify({"error": "patient_validation_unavailable"}), 503
            patient = ensure_patient_access(database, patient_id, user=user)
            linked_patient_id = patient.id

        report = analyzer.analyze(
            image,
            manual_roi_mask=manual_roi_mask,
            manual_roi_masks=manual_roi_masks,
            roi_metadata=manual_roi_summary,
            roi_metadata_list=manual_roi_metadata_list,
        )
        generated_at = datetime.now(timezone.utc).isoformat()
        result = build_headless_analyzer_result(
            report,
            analysis_id=analysis_id,
            patient_id=linked_patient_id or "",
            image_filename=validated_image.original_name or "unknown",
            image_content_type=validated_image.mime_type,
            generated_at=generated_at,
        )
        if manual_roi_summary and not result.get("roi"):
            result["roi"] = manual_roi_summary
        if manual_roi_metadata_list and not result.get("rois"):
            result["rois"] = manual_roi_metadata_list

        if len(manual_roi_metadata_list) > 1:
            detection_label = f"{len(manual_roi_metadata_list)} ROIs manuais confirmadas"
            detection_description = (
                "Multiplas delimitacoes manuais foram confirmadas e unidas como filtro principal da analise."
            )
        elif manual_roi_summary:
            detection_label = "ROI manual confirmada"
            detection_description = (
                "Delimitacao manual confirmada pelo usuario e aplicada como filtro principal da analise."
            )
        else:
            detection_label = "Regiao analisada"
            detection_description = "Contorno e area considerada pela IA para a leitura clinica."
        result["visuals"] = {
            "detection": encode_visual_payload(
                getattr(report, "detection_overlay", None),
                label=detection_label,
                description=detection_description,
            ),
            "segmentation": encode_visual_payload(
                getattr(report, "segmentation_map", None),
                label="Mapa de tecidos",
                description=(
                    "Distribuicao de tecidos identificados pela segmentacao clinica. "
                    "Azul-ardosia indica area interna da ROI mantida como incerta."
                ),
                mime_type="image/png",
            ),
            "combined": encode_visual_payload(
                getattr(report, "tissue_overlay", None),
                label="Visualizacao combinada",
                description=(
                    "Foto original combinada com a leitura visual da IA; "
                    "azul-ardosia indica area incerta, nao tecido ausente."
                ),
            ),
            "attention": encode_visual_payload(
                getattr(report, "grad_cam_overlay", None),
                label="Mapa de atencao da IA",
                description="Areas em vermelho indicam onde a rede concentrou maior relevancia.",
            ),
        }
        result = _to_json_safe(result)

        try:
            db = get_firestore_db()
            roi_mask_storage_path = None
            mask_bytes = _mask_to_png_bytes(manual_roi_mask) if manual_roi_mask is not None else b""
            bucket = None
            if mask_bytes or validated_image.content:
                try:
                    bucket = get_storage_bucket()
                except Exception:
                    bucket = None

            if bucket is not None:
                try:
                    blob = bucket.blob(f"analyses/{analysis_id}/image{validated_image.extension}")
                    blob.upload_from_string(validated_image.content, content_type=validated_image.mime_type)
                except Exception:
                    pass

                if mask_bytes:
                    try:
                        roi_mask_storage_path = f"analyses/{analysis_id}/roi_mask.png"
                        mask_blob = bucket.blob(roi_mask_storage_path)
                        mask_blob.upload_from_string(mask_bytes, content_type="image/png")
                    except Exception:
                        roi_mask_storage_path = None

            if roi_mask_storage_path and isinstance(result.get("roi"), dict):
                result["roi"]["storage_path"] = roi_mask_storage_path

            doc_data = {
                **result,
                "id": analysis_id,
                "patient_id": linked_patient_id,
                "owner_uid": owner_uid,
                "created_at": generated_at,
                "image_filename": validated_image.original_name or "unknown",
            }
            db.collection("analyses").document(analysis_id).set(doc_data)
        except Exception:
            pass

        return jsonify(result)

    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": "analysis_failed", "detail": str(exc)}), 500


@integration_api.route("/image-labels", methods=["POST"])
def image_labels():
    current_user_required()
    enforce_rate_limit("label", 20)
    if "image" not in request.files:
        return jsonify({"error": "missing_image", "detail": "Campo 'image' obrigatorio"}), 400

    image_file = request.files["image"]
    try:
        validated_image = validate_and_sanitize_image_upload(image_file)
        img = Image.open(io.BytesIO(validated_image.content))
        model = _init_gemini()
        if model is None:
            return jsonify(
                {
                    "labels": [{"description": "Imagem medica", "confidence": 0.8}],
                    "source": "fallback",
                    "detail": "Gemini nao configurado",
                }
            )

        prompt_content = [
            "Analise esta imagem e retorne um JSON com a chave 'labels' contendo "
            "uma lista de objetos com 'description' e 'confidence'. Retorne APENAS o JSON.",
            img,
        ]
        best_response = _generate_best_response(
            prompt_content,
            system_instruction=_GEMINI_SYSTEM_INSTRUCTION,
            is_json=True
        )

        if not best_response:
            return jsonify(
                {
                    "labels": [{"description": "Imagem medica", "confidence": 0.8}],
                    "source": "fallback",
                    "detail": "Nenhum modelo Gemini respondeu",
                }
            )

        try:
            text = best_response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            labels_data = json.loads(text)
        except (json.JSONDecodeError, IndexError):
            labels_data = {"labels": [{"description": best_response[:200], "confidence": 0.9}]}

        labels_data["source"] = "gemini-vision"
        return jsonify(labels_data)
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": "labeling_failed", "detail": str(exc)}), 500


@integration_api.route("/ai-chat", methods=["POST"])
def ai_chat():
    user = current_user_required()
    enforce_rate_limit("chat", 60)
    data = validate_json_request(AIChatPayload).model_dump()

    user_message = data["message"]
    conversation_id = data.get("conversation_id") or str(uuid.uuid4())
    context = data.get("context", {}) or {}
    owner_uid = user_uid(user)
    patient_id = context.get("patient_id")
    if patient_id:
        database = current_app.extensions.get("redisus_db")
        if database is None:
            return jsonify({"error": "patient_validation_unavailable"}), 503
        ensure_patient_access(database, patient_id, user=user)

    try:
        firestore_context = ""
        history_docs = []
        try:
            db = get_firestore_db()
            conv_ref = db.collection("ai_conversations").document(conversation_id)
            existing = conv_ref.get()
            if existing.exists:
                existing_data = existing.to_dict() or {}
                if not is_admin(user) and existing_data.get("owner_uid") != owner_uid:
                     return jsonify({"error": "conversation_access_denied"}), 403

            history_ref = (
                db.collection("ai_conversations").document(conversation_id).collection("messages").order_by("timestamp").limit(20)
            )
            history_docs = list(history_ref.stream())
            if history_docs:
                history_text = "\n".join(
                    [
                        f"{'Usuario' if m.to_dict().get('role') == 'user' else 'Assistente'}: {m.to_dict().get('content', '')}"
                        for m in history_docs[-10:]
                    ]
                )
                firestore_context += f"\n\nHistorico da conversa:\n{history_text}"
        except Exception:
            pass

        model = _init_gemini()
        if model is not None:
            prompt = user_message
            if firestore_context:
                prompt = f"Contexto do system:\n{firestore_context}\n\nPergunta do usuario: {user_message}"
            ai_response = _generate_best_response(
                prompt,
                system_instruction=_GEMINI_SYSTEM_INSTRUCTION,
                is_json=False
            )
            if not ai_response:
                ai_response = _rule_based_response(user_message)
        else:
            ai_response = _rule_based_response(user_message)

        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            db = get_firestore_db()
            conv_ref = db.collection("ai_conversations").document(conversation_id)
            conv_ref.set(
                {
                    "id": conversation_id,
                    "owner_uid": owner_uid,
                    "updated_at": timestamp,
                    "last_message": user_message[:100],
                    "message_count": len(history_docs) + 2,
                    "updated_by": user_display_name(user),
                },
                merge=True,
            )
            messages_ref = conv_ref.collection("messages")
            messages_ref.add(
                {
                    "role": "user",
                    "content": user_message,
                    "timestamp": timestamp,
                    "owner_uid": owner_uid,
                }
            )
            messages_ref.add(
                {
                    "role": "assistant",
                    "content": ai_response,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "owner_uid": owner_uid,
                }
            )
        except Exception:
            pass

        return jsonify(
            {
                "response": ai_response,
                "conversation_id": conversation_id,
                "timestamp": timestamp,
                "source": "gemini" if model else "rules",
            }
        )
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": "chat_failed", "detail": str(exc)}), 500


@integration_api.route("/ai-chat/history", methods=["GET"])
def chat_history():
    user = current_user_required()
    try:
        db = get_firestore_db()
        query = db.collection("ai_conversations")
        if not is_admin(user):
            query = query.where("owner_uid", "==", user_uid(user))
        convs = query.order_by("updated_at", direction="DESCENDING").limit(50).stream()
        result = []
        for doc in convs:
            data = doc.to_dict()
            result.append(
                {
                    "id": doc.id,
                    "last_message": data.get("last_message", ""),
                    "updated_at": data.get("updated_at", ""),
                    "message_count": data.get("message_count", 0),
                }
            )
        return jsonify({"conversations": result})
    except Exception as exc:
        return jsonify({"conversations": [], "error": str(exc)})


@integration_api.route("/ai-chat/history/<conversation_id>", methods=["GET"])
def chat_messages(conversation_id: str):
    user = current_user_required()
    try:
        db = get_firestore_db()
        conv_ref = db.collection("ai_conversations").document(conversation_id)
        conv_doc = conv_ref.get()
        if not conv_doc.exists:
            return jsonify({"messages": [], "error": "conversation_not_found"}), 404
        conv_data = conv_doc.to_dict() or {}
        if not is_admin(user) and conv_data.get("owner_uid") != user_uid(user):
            return jsonify({"messages": [], "error": "conversation_access_denied"}), 403
        messages = (
            conv_ref.collection("messages").order_by("timestamp").stream()
        )
        result = []
        for doc in messages:
            data = doc.to_dict()
            result.append(
                {
                    "id": doc.id,
                    "role": data.get("role", ""),
                    "content": data.get("content", ""),
                    "timestamp": data.get("timestamp", ""),
                }
            )
        return jsonify({"messages": result, "conversation_id": conversation_id})
    except Exception as exc:
        return jsonify({"messages": [], "error": str(exc)})


@integration_api.route("/ai-chat/history/<conversation_id>", methods=["DELETE"])
def delete_conversation(conversation_id: str):
    user = current_user_required()
    try:
        db = get_firestore_db()
        conv_ref = db.collection("ai_conversations").document(conversation_id)
        conv_doc = conv_ref.get()
        if not conv_doc.exists:
            return jsonify({"error": "conversation_not_found"}), 404
        conv_data = conv_doc.to_dict() or {}
        if not is_admin(user) and conv_data.get("owner_uid") != user_uid(user):
            return jsonify({"error": "conversation_access_denied"}), 403
        messages = conv_ref.collection("messages").stream()
        for msg in messages:
            msg.reference.delete()
        conv_ref.delete()
        return jsonify({"deleted": True, "conversation_id": conversation_id})
    except Exception as exc:
        return jsonify({"error": "delete_failed", "detail": str(exc)}), 500


@integration_api.route("/patients", methods=["GET"])
def list_patients():
    try:
        user = current_user_required()
        database = current_app.extensions.get("redisus_db")
        if database is None:
            return jsonify({"patients": [], "error": "database_unavailable"}), 503
        patients = database.list_patients()
        scoped = filter_patients_for_user(patients, user=user)
        result = [patient.to_dict() if hasattr(patient, "to_dict") else patient for patient in scoped]
        return jsonify({"patients": result})
    except Exception as exc:
        return jsonify({"patients": [], "error": str(exc)})


@integration_api.route("/generate-pdf", methods=["POST"])
def generate_pdf():
    current_user_required()
    enforce_rate_limit("report", 10)
    try:
        if request.mimetype != "application/json":
            abort(415, description="content-type must be application/json")
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            abort(400, description="invalid or empty json payload")
        if set(data) - {"latex_code"}:
            abort(400, description="unexpected fields in PDF request")
        latex_code = data.get("latex_code")
        if not isinstance(latex_code, str) or not latex_code.strip():
            abort(400, description="latex_code is required")
        if len(latex_code) > 1_500_000:
            abort(413, description="latex source exceeds maximum size")
        _validate_latex_commands(latex_code)

        with tempfile.TemporaryDirectory(prefix="heal_pdf_") as tmpdir:
            workdir = Path(tmpdir).resolve()
            latex_code = _prepare_latex_images(latex_code, workdir)
            tex_path = workdir / "report.tex"
            tex_path.write_text(latex_code, encoding="utf-8")

            command = [
                "pdflatex",
                "-no-shell-escape",
                "-halt-on-error",
                "-interaction=nonstopmode",
                "-output-directory",
                str(workdir),
                tex_path.name,
            ]
            tex_environment = os.environ.copy()
            tex_environment.update(
                {
                    "openin_any": "p",
                    "openout_any": "p",
                    "TEXMFOUTPUT": str(workdir),
                }
            )
            result = None
            for _ in range(2):
                result = subprocess.run(
                    command,
                    cwd=workdir,
                    env=tex_environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if result.returncode != 0:
                    break

            pdf_path = workdir / "report.pdf"
            if result is None or result.returncode != 0 or not pdf_path.is_file():
                return _problem_response(
                    status=422,
                    code="pdf_compilation_failed",
                    title="Falha ao compilar PDF",
                    detail="O conteúdo do relatório não pôde ser compilado com segurança.",
                )
            if pdf_path.stat().st_size > 20 * 1024 * 1024:
                abort(413, description="generated PDF exceeds maximum size")
            pdf_bytes = pdf_path.read_bytes()

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="relatorio_clinico.pdf",
        )
    except ValueError as exc:
        abort(400, description=str(exc))
    except subprocess.TimeoutExpired:
        return _problem_response(
            status=504,
            code="pdf_compilation_timeout",
            title="Tempo de compilação excedido",
            detail="A compilação segura do relatório excedeu o limite de tempo.",
        )
    except Exception as exc:
        current_app.logger.exception("PDF generation failed")
        raise exc
