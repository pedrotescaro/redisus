# -*- coding: utf-8 -*-
"""Integration routes consolidated from the legacy backend app."""

from __future__ import annotations

import io
import json
import os
import traceback
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import Blueprint, current_app, jsonify, request
from PIL import Image

from packages.clinical_domain.workflow import DEFAULT_MODEL_VERSION, normalize_ai_output
from packages.clinical_domain.validation import (
    AIChatPayload,
    assert_allowed_form_fields,
    validate_and_sanitize_image_upload,
    validate_json_request,
)
from packages.shared.runtime import load_project_env
from packages.shared.security import (
    current_user,
    current_user_required,
    enforce_rate_limit,
    ensure_patient_access,
    filter_patients_for_user,
    is_admin,
    user_display_name,
    user_uid,
)

load_project_env()

from backend.firebase_admin_setup import get_firestore_db, get_storage_bucket, is_firebase_ready  # noqa: E402

integration_api = Blueprint("integration_api", __name__, url_prefix="/api/v1")

_gemini_model = None
_wound_analyzer = None


_TISSUE_KEY_ALIASES = {
    "coagulation necrosis (eschar)": "necrosis",
    "necrose de coagulacao (escara)": "necrosis",
    "slough (fibrin)": "slough",
    "esfacelo (fibrina)": "slough",
    "granulation tissue": "granulation",
    "tecido de granulacao": "granulation",
}


def _init_gemini():
    global _gemini_model
    if _gemini_model is not None:
        return _gemini_model

    try:
        import google.generativeai as genai

        api_key = os.getenv("GOOGLE_AI_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        _gemini_model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=(
                "Voce e o assistente de IA HEAL+ da plataforma REDISUS. "
                "Especialista em estomaterapia, analise de feridas, cicatrizacao "
                "e cuidados clinicos com feridas cronicas. "
                "Responda em portugues brasileiro, de forma tecnica mas acessivel. "
                "Seja conciso e direto nas respostas."
            ),
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


def _slugify_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    normalized: list[str] = []
    for char in text:
        if unicodedata.category(char) == "Mn":
            continue
        if char.isalnum():
            normalized.append(char)
        elif normalized and normalized[-1] != " ":
            normalized.append(" ")
    return " ".join("".join(normalized).split())


def _serialize_legacy_report(report: Any) -> Dict[str, Any]:
    result = {
        "is_valid_wound": bool(getattr(report, "is_valid_wound", False)),
        "rejection_reason": getattr(report, "rejection_reason", "") or "",
        "primary_tissue": getattr(report, "primary_tissue", "") or "",
        "primary_justification": getattr(report, "primary_justification", "") or "",
        "wound_area_px": int(getattr(report, "wound_area_px", 0) or 0),
        "health_score": float(getattr(report, "health_score", 0.0) or 0.0),
        "processing_time_ms": float(getattr(report, "processing_time_ms", 0.0) or 0.0),
        "tissues": [],
        "border_analysis": None,
    }

    for tissue in getattr(report, "tissues", []) or []:
        result["tissues"].append(
            {
                "name": tissue.name,
                "name_en": tissue.name_en,
                "percentage": tissue.percentage,
                "color_hex": tissue.color_hex,
                "description": tissue.description,
                "clinical_action": tissue.clinical_action,
            }
        )

    border = getattr(report, "border_analysis", None)
    if border:
        result["border_analysis"] = {
            "maceration": border.maceration,
            "inflammation": border.inflammation,
            "regular_borders": border.regular_borders,
            "description": border.description,
        }

    for field in (
        "dl_prediction",
        "resnet_prediction",
        "ensemble_classification",
        "body_part",
        "push_score",
        "lighting_analysis",
    ):
        value = getattr(report, field, None)
        if value:
            result[field] = value

    return result


def _extract_tissue_percentages(report: Any) -> Dict[str, float]:
    tissue_percentages = {"granulation": 0.0, "slough": 0.0, "necrosis": 0.0}
    for tissue in getattr(report, "tissues", []) or []:
        label = _slugify_text(getattr(tissue, "name_en", "") or getattr(tissue, "name", ""))
        key = _TISSUE_KEY_ALIASES.get(label)
        if key:
            tissue_percentages[key] = round(float(getattr(tissue, "percentage", 0.0) or 0.0), 2)
    return tissue_percentages


def _resolve_report_etiology(report: Any) -> str:
    resnet_prediction = getattr(report, "resnet_prediction", None) or {}
    if resnet_prediction.get("mapped_etiology"):
        return str(resnet_prediction["mapped_etiology"])

    final_class = str(resnet_prediction.get("final_class") or "").strip()
    if final_class:
        return final_class

    dl_prediction = getattr(report, "dl_prediction", None) or {}
    if dl_prediction.get("class_name"):
        return str(dl_prediction["class_name"])

    ensemble_prediction = getattr(report, "ensemble_classification", None) or {}
    if ensemble_prediction.get("class_name"):
        return str(ensemble_prediction["class_name"])

    return "unspecified_wound"


def _resolve_report_confidence(report: Any) -> float:
    resnet_prediction = getattr(report, "resnet_prediction", None) or {}
    if resnet_prediction.get("final_confidence") is not None:
        return float(resnet_prediction.get("final_confidence") or 0.0)

    dl_prediction = getattr(report, "dl_prediction", None) or {}
    if dl_prediction.get("confidence") is not None:
        return float(dl_prediction.get("confidence") or 0.0)

    ensemble_prediction = getattr(report, "ensemble_classification", None) or {}
    if ensemble_prediction.get("confidence") is not None:
        return float(ensemble_prediction.get("confidence") or 0.0)

    return 0.0


def _resolve_model_version(report: Any) -> str:
    if getattr(report, "resnet_prediction", None):
        return "heal-analyzer-headless-resnet"
    if getattr(report, "dl_prediction", None):
        return "heal-analyzer-headless-dl"
    if getattr(report, "ensemble_classification", None):
        return "heal-analyzer-headless-ensemble"
    return DEFAULT_MODEL_VERSION


def _build_workflow_raw_output(report: Any) -> Dict[str, Any]:
    confidence = max(0.0, min(1.0, _resolve_report_confidence(report)))
    fallback_used = not bool(
        getattr(report, "resnet_prediction", None)
        or getattr(report, "dl_prediction", None)
        or getattr(report, "ensemble_classification", None)
    )
    resnet_prediction = getattr(report, "resnet_prediction", None) or {}
    primary_tissue = getattr(report, "primary_tissue", "") or "Unspecified wound"
    primary_justification = getattr(report, "primary_justification", "") or getattr(report, "rejection_reason", "")
    recommendations = []
    for tissue in getattr(report, "tissues", []) or []:
        if getattr(tissue, "percentage", 0.0) and getattr(tissue, "percentage", 0.0) > 0:
            action = str(getattr(tissue, "clinical_action", "") or "").strip()
            if action:
                recommendations.append(action)
                break
    if not recommendations:
        recommendations.append("Validar clinicamente o resultado antes de tomada de decisao.")

    metadata = {
        "source": "integration_headless_analyzer",
        "wound_area_px": int(getattr(report, "wound_area_px", 0) or 0),
        "primary_tissue": primary_tissue,
        "is_valid_wound": bool(getattr(report, "is_valid_wound", False)),
    }
    if getattr(report, "body_part", None):
        metadata["body_part"] = dict(getattr(report, "body_part") or {})
    if getattr(report, "lighting_analysis", None):
        metadata["lighting_analysis"] = dict(getattr(report, "lighting_analysis") or {})

    raw_output = {
        "etiology": _resolve_report_etiology(report),
        "confidence": confidence,
        "tissue_percentages": _extract_tissue_percentages(report),
        "wound_area_cm2": 0.0,
        "diagnosis_summary": primary_justification or f"{primary_tissue} identified in headless integration analysis.",
        "recommendations": recommendations,
        "fallback_used": fallback_used,
        "needs_expert_review": bool(resnet_prediction.get("needs_expert_review")) or fallback_used or confidence < 0.8,
        "confidence_level": str(resnet_prediction.get("confidence_level") or ""),
        "confidence_entropy": float(resnet_prediction.get("confidence_entropy") or 0.0),
        "confidence_margin": float(resnet_prediction.get("confidence_margin") or 0.0),
        "metadata": metadata,
    }
    if not getattr(report, "is_valid_wound", False):
        raw_output["diagnosis_summary"] = getattr(report, "rejection_reason", "") or "Image rejected by analyzer."
        raw_output["needs_expert_review"] = True
        raw_output["fallback_used"] = True
    return raw_output


def _build_integration_evaluation_context(
    *,
    analysis_id: str,
    patient_id: str,
    generated_at: str,
    raw_output: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "id": analysis_id,
        "patient_id": patient_id,
        "evaluation_date": generated_at,
        "wound_type": raw_output.get("etiology"),
        "wound_area_cm2": raw_output.get("wound_area_cm2", 0.0),
        "depth_mm": 0.0,
        "pain_score": 0.0,
        "tissue_composition": dict(raw_output.get("tissue_percentages") or {}),
    }


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


@integration_api.route("/analyze", methods=["POST"])
def analyze_image():
    user = current_user_required()
    enforce_rate_limit("analyze", 20)
    if "image" not in request.files:
        return jsonify({"error": "missing_image", "detail": "Campo 'image' obrigatorio"}), 400

    image_file = request.files["image"]
    assert_allowed_form_fields(request.form, allowed={"patient_id"})
    patient_id = (request.form.get("patient_id") or "").strip()

    try:
        import cv2
        import numpy as np

        validated_image = validate_and_sanitize_image_upload(image_file)
        image = cv2.cvtColor(np.array(Image.open(io.BytesIO(validated_image.content)).convert("RGB")), cv2.COLOR_RGB2BGR)

        analyzer = _get_wound_analyzer()
        if analyzer is None:
            return jsonify({"error": "analyzer_unavailable", "detail": "Modelo de analise nao disponivel"}), 503

        analysis_id = str(uuid.uuid4())
        owner_uid = user_uid(user)
        linked_patient_id = None
        if patient_id:
            database = current_app.extensions.get("redisus_db")
            if database is None:
                return jsonify({"error": "patient_validation_unavailable"}), 503
            patient = ensure_patient_access(database, patient_id, user=user)
            linked_patient_id = patient.id

        report = analyzer.analyze(image)
        generated_at = datetime.now(timezone.utc).isoformat()
        legacy_result = _serialize_legacy_report(report)
        raw_output = _build_workflow_raw_output(report)
        evaluation_context = _build_integration_evaluation_context(
            analysis_id=analysis_id,
            patient_id=linked_patient_id or "",
            generated_at=generated_at,
            raw_output=raw_output,
        )
        official_result = normalize_ai_output(
            raw_output,
            patient_id=linked_patient_id or "",
            lesion_id=analysis_id,
            evaluation=evaluation_context,
            fallback_used=bool(raw_output.get("fallback_used")),
            model_version=_resolve_model_version(report),
            generated_at=generated_at,
        )
        official_result.setdefault("metadata", {}).update(
            {
                "analysis_id": analysis_id,
                "image_filename": validated_image.original_name or "unknown",
                "image_content_type": validated_image.mime_type,
            }
        )
        result = {
            **official_result,
            **legacy_result,
            "analysis_id": analysis_id,
        }

        try:
            db = get_firestore_db()
            doc_data = {
                **result,
                "id": analysis_id,
                "patient_id": linked_patient_id,
                "owner_uid": owner_uid,
                "created_at": generated_at,
                "image_filename": validated_image.original_name or "unknown",
            }
            db.collection("analyses").document(analysis_id).set(doc_data)
            try:
                bucket = get_storage_bucket()
                blob = bucket.blob(f"analyses/{analysis_id}/image{validated_image.extension}")
                blob.upload_from_string(validated_image.content, content_type=validated_image.mime_type)
            except Exception:
                pass
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

        response = model.generate_content(
            [
                "Analise esta imagem e retorne um JSON com a chave 'labels' contendo "
                "uma lista de objetos com 'description' e 'confidence'. Retorne APENAS o JSON.",
                img,
            ]
        )

        try:
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            labels_data = json.loads(text)
        except (json.JSONDecodeError, IndexError):
            labels_data = {"labels": [{"description": response.text[:200], "confidence": 0.9}]}

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
                prompt = f"Contexto do sistema:\n{firestore_context}\n\nPergunta do usuario: {user_message}"
            response = model.generate_content(prompt)
            ai_response = response.text
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
