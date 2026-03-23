# -*- coding: utf-8 -*-
"""
HEAL+ / REDISUS - Backend API Flask
"""
import sys
import os
import io
import json
import time
import uuid
import base64
import traceback
from pathlib import Path
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# IMPORTANTE: carregar .env ANTES de importar firebase_admin_setup
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / "backend" / ".env.local", override=True)
load_dotenv(ROOT_DIR / "backend" / ".env", override=True)
load_dotenv(ROOT_DIR / ".env")

from flask import Flask, request, jsonify
from flask_cors import CORS

from backend.firebase_admin_setup import (
    get_firestore_db,
    get_storage_bucket,
    verify_id_token,
)

app = Flask(__name__)
CORS(app, 
    origins="*",
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    supports_credentials=False,
)

_gemini_model = None

def _init_gemini():
    global _gemini_model
    if _gemini_model is not None:
        return _gemini_model
    try:
        import google.generativeai as genai
        api_key = os.getenv("GOOGLE_AI_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("[Gemini] [!] Sem GOOGLE_AI_API_KEY - chat IA usara respostas baseadas em regras")
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
        print("[Gemini] [OK] Modelo inicializado (gemini-2.0-flash)")
        return _gemini_model
    except Exception as e:
        print(f"[Gemini] Erro ao inicializar: {e}")
        return None


_wound_analyzer = None

def _get_wound_analyzer():
    global _wound_analyzer
    if _wound_analyzer is not None:
        return _wound_analyzer
    try:
        from heal_analyzer import ClinicalWoundAnalyzer
        _wound_analyzer = ClinicalWoundAnalyzer()
        print("[HEAL+] [OK] ClinicalWoundAnalyzer carregado")
        return _wound_analyzer
    except Exception as e:
        print(f"[HEAL+] Erro ao carregar analyzer: {e}")
        return None


def get_current_user():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    try:
        decoded = verify_id_token(token)
        return decoded
    except Exception:
        return None


def require_auth(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({"error": "unauthorized", "detail": "Token invalido ou ausente"}), 401
        request.firebase_user = user
        return f(*args, **kwargs)
    return decorated


@app.route("/api/v1/health", methods=["GET"])
def health():
    gemini_ready = _gemini_model is not None or _init_gemini() is not None
    analyzer_status = "available" if _wound_analyzer is not None else "not_loaded"
    return jsonify({
        "status": "ok",
        "service": "heal-redisus-api",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "gemini": "ready" if gemini_ready else "unconfigured",
            "wound_analyzer": analyzer_status,
            "firebase": "configured",
        }
    })


@app.route("/api/v1/analyze", methods=["POST"])
def analyze_image():
    if "image" not in request.files:
        return jsonify({"error": "missing_image", "detail": "Campo 'image' obrigatorio"}), 400

    image_file = request.files["image"]
    patient_id = request.form.get("patient_id", "")

    try:
        import cv2
        import numpy as np

        img_bytes = image_file.read()
        nparr = np.frombuffer(img_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return jsonify({"error": "invalid_image", "detail": "Nao foi possivel decodificar a imagem"}), 400

        analyzer = _get_wound_analyzer()
        if analyzer is None:
            return jsonify({"error": "analyzer_unavailable", "detail": "Modelo de analise nao disponivel"}), 503

        report = analyzer.analyze(image)

        result = {
            "is_valid_wound": report.is_valid_wound,
            "rejection_reason": report.rejection_reason,
            "primary_tissue": report.primary_tissue,
            "primary_justification": report.primary_justification,
            "wound_area_px": report.wound_area_px,
            "health_score": report.health_score,
            "processing_time_ms": report.processing_time_ms,
            "tissues": [],
            "border_analysis": None,
        }

        for tissue in report.tissues:
            result["tissues"].append({
                "name": tissue.name,
                "name_en": tissue.name_en,
                "percentage": tissue.percentage,
                "color_hex": tissue.color_hex,
                "description": tissue.description,
                "clinical_action": tissue.clinical_action,
            })

        if report.border_analysis:
            result["border_analysis"] = {
                "maceration": report.border_analysis.maceration,
                "inflammation": report.border_analysis.inflammation,
                "regular_borders": report.border_analysis.regular_borders,
                "description": report.border_analysis.description,
            }

        if report.dl_prediction:
            result["dl_prediction"] = report.dl_prediction
        if report.resnet_prediction:
            result["resnet_prediction"] = report.resnet_prediction
        if report.ensemble_classification:
            result["ensemble_classification"] = report.ensemble_classification
        if report.body_part:
            result["body_part"] = report.body_part
        if report.push_score:
            result["push_score"] = report.push_score
        if report.lighting_analysis:
            result["lighting_analysis"] = report.lighting_analysis

        analysis_id = str(uuid.uuid4())
        try:
            db = get_firestore_db()
            doc_data = {
                **result,
                "id": analysis_id,
                "patient_id": patient_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "image_filename": image_file.filename or "unknown",
            }
            db.collection("analyses").document(analysis_id).set(doc_data)
            try:
                bucket = get_storage_bucket()
                blob = bucket.blob(f"analyses/{analysis_id}/{image_file.filename or 'image.jpg'}")
                blob.upload_from_string(img_bytes, content_type=image_file.content_type or "image/jpeg")
                result["image_url"] = blob.public_url
            except Exception as storage_err:
                print(f"[Storage] Upload falhou: {storage_err}")
        except Exception as db_err:
            print(f"[Firestore] Salvar analise falhou: {db_err}")

        result["analysis_id"] = analysis_id
        return jsonify(result)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "analysis_failed", "detail": str(e)}), 500


@app.route("/api/v1/image-labels", methods=["POST"])
def image_labels():
    if "image" not in request.files:
        return jsonify({"error": "missing_image", "detail": "Campo 'image' obrigatorio"}), 400

    image_file = request.files["image"]
    try:
        import PIL.Image
        img_bytes = image_file.read()
        img = PIL.Image.open(io.BytesIO(img_bytes))

        model = _init_gemini()
        if model is None:
            return jsonify({
                "labels": [{"description": "Imagem medica", "confidence": 0.8}],
                "source": "fallback",
                "detail": "Gemini nao configurado"
            })

        response = model.generate_content([
            "Analise esta imagem e retorne um JSON com a chave 'labels' contendo "
            "uma lista de objetos com 'description' (texto descritivo do conteudo) "
            "e 'confidence' (float 0-1). Retorne APENAS o JSON, sem markdown.",
            img,
        ])

        try:
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            labels_data = json.loads(text)
        except (json.JSONDecodeError, IndexError):
            labels_data = {"labels": [{"description": response.text[:200], "confidence": 0.9}]}

        labels_data["source"] = "gemini-vision"
        return jsonify(labels_data)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "labeling_failed", "detail": str(e)}), 500


@app.route("/api/v1/ai-chat", methods=["POST"])
def ai_chat():
    data = request.get_json(silent=True)
    if not data or not data.get("message"):
        return jsonify({"error": "missing_message", "detail": "Campo 'message' obrigatorio"}), 400

    user_message = data["message"]
    conversation_id = data.get("conversation_id") or str(uuid.uuid4())
    context = data.get("context", {})

    try:
        firestore_context = ""
        history_docs = []
        try:
            db = get_firestore_db()
            if context.get("patient_id"):
                patient_doc = db.collection("patients").document(context["patient_id"]).get()
                if patient_doc.exists:
                    patient_data = patient_doc.to_dict()
                    firestore_context += f"\n\nDados do paciente:\n{json.dumps(patient_data, ensure_ascii=False, default=str)}"

            history_ref = (
                db.collection("ai_conversations")
                .document(conversation_id)
                .collection("messages")
                .order_by("timestamp")
                .limit(20)
            )
            history_docs = list(history_ref.stream())
            if history_docs:
                history_text = "\n".join([
                    f"{'Usuario' if m.to_dict().get('role') == 'user' else 'Assistente'}: {m.to_dict().get('content', '')}"
                    for m in history_docs[-10:]
                ])
                firestore_context += f"\n\nHistorico da conversa:\n{history_text}"
        except Exception as db_err:
            print(f"[Firestore] Contexto falhou: {db_err}")

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
            conv_ref.set({
                "id": conversation_id,
                "updated_at": timestamp,
                "last_message": user_message[:100],
                "message_count": len(history_docs) + 2,
            }, merge=True)
            messages_ref = conv_ref.collection("messages")
            messages_ref.add({"role": "user", "content": user_message, "timestamp": timestamp})
            messages_ref.add({"role": "assistant", "content": ai_response, "timestamp": datetime.now(timezone.utc).isoformat()})
        except Exception as save_err:
            print(f"[Firestore] Salvar chat falhou: {save_err}")

        return jsonify({
            "response": ai_response,
            "conversation_id": conversation_id,
            "timestamp": timestamp,
            "source": "gemini" if model else "rules",
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "chat_failed", "detail": str(e)}), 500


def _rule_based_response(message: str) -> str:
    msg = message.lower()
    if any(w in msg for w in ["ferida", "ulcera", "lesao", "wound"]):
        return (
            "Para analise de feridas, recomendo fazer upload de uma foto na secao "
            "de avaliacoes. O sistema HEAL+ utiliza IA com modelos ResNet50, "
            "DermaIntel e BiomedCLIP para classificar o tipo de tecido, "
            "avaliar cicatrizacao e sugerir condutas clinicas.\n\n"
            "Posso ajudar com:\n"
            "- Classificacao tecidual (necrose, esfacelo, granulacao, epitelizacao)\n"
            "- Escalas clinicas (PUSH, BWAT, Braden)\n"
            "- Recomendacoes de curativo\n"
            "- Monitoramento de evolucao"
        )
    elif any(w in msg for w in ["paciente", "historico", "buscar", "maria", "joao"]):
        return (
            "Posso pesquisar informacoes de pacientes no banco de dados. "
            "Para acessar o historico completo, va ate a secao 'Pacientes' "
            "no menu lateral.\n\n"
            "Funcionalidades disponiveis:\n"
            "- Busca por nome ou ID\n"
            "- Historico completo de avaliacoes\n"
            "- Relatorios de evolucao\n"
            "- Comparacao temporal de feridas"
        )
    elif any(w in msg for w in ["relatorio", "report", "pdf", "exportar"]):
        return (
            "Para gerar relatorios, acesse a secao 'Relatorios' no menu. "
            "Voce pode gerar:\n\n"
            "- Relatorio individual de avaliacao\n"
            "- Relatorio de evolucao temporal\n"
            "- Relatorio comparativo\n"
            "- Exportacao em PDF"
        )
    elif any(w in msg for w in ["ola", "oi", "bom dia", "boa tarde", "boa noite", "hello"]):
        return (
            "Ola! Sou o assistente de IA do HEAL+, a plataforma REDISUS.\n\n"
            "Posso ajudar voce com:\n"
            "* Analise de imagens de feridas\n"
            "* Consultar dados de pacientes\n"
            "* Gerar relatorios clinicos\n"
            "* Informacoes sobre estomaterapia\n"
            "* Duvidas sobre a plataforma\n\n"
            "Como posso ajuda-lo hoje?"
        )
    else:
        return (
            "Entendi sua pergunta. Como assistente HEAL+, posso ajudar com:\n\n"
            "- **Analise de feridas**: Faca upload de uma imagem para analise com IA\n"
            "- **Pacientes**: Busque historico e dados clinicos\n"
            "- **Relatorios**: Gere e exporte relatorios\n"
            "- **Protocolos**: Consulte condutas e protocolos clinicos\n\n"
            "Poderia reformular sua pergunta ou ser mais especifico?"
        )


@app.route("/api/v1/ai-chat/history", methods=["GET"])
def chat_history():
    try:
        db = get_firestore_db()
        convs = db.collection("ai_conversations").order_by("updated_at", direction="DESCENDING").limit(50).stream()
        result = []
        for doc in convs:
            data = doc.to_dict()
            result.append({
                "id": doc.id,
                "last_message": data.get("last_message", ""),
                "updated_at": data.get("updated_at", ""),
                "message_count": data.get("message_count", 0),
            })
        return jsonify({"conversations": result})
    except Exception as e:
        return jsonify({"conversations": [], "error": str(e)})


@app.route("/api/v1/ai-chat/history/<conversation_id>", methods=["GET"])
def chat_messages(conversation_id: str):
    try:
        db = get_firestore_db()
        messages = db.collection("ai_conversations").document(conversation_id).collection("messages").order_by("timestamp").stream()
        result = []
        for doc in messages:
            data = doc.to_dict()
            result.append({"id": doc.id, "role": data.get("role", ""), "content": data.get("content", ""), "timestamp": data.get("timestamp", "")})
        return jsonify({"messages": result, "conversation_id": conversation_id})
    except Exception as e:
        return jsonify({"messages": [], "error": str(e)})


@app.route("/api/v1/ai-chat/history/<conversation_id>", methods=["DELETE"])
def delete_conversation(conversation_id: str):
    try:
        db = get_firestore_db()
        conv_ref = db.collection("ai_conversations").document(conversation_id)
        messages = conv_ref.collection("messages").stream()
        for msg in messages:
            msg.reference.delete()
        conv_ref.delete()
        return jsonify({"deleted": True, "conversation_id": conversation_id})
    except Exception as e:
        return jsonify({"error": "delete_failed", "detail": str(e)}), 500


@app.route("/api/v1/patients", methods=["GET"])
def list_patients():
    try:
        db = get_firestore_db()
        patients = db.collection("patients").order_by("name").stream()
        result = []
        for doc in patients:
            data = doc.to_dict()
            data["id"] = doc.id
            result.append(data)
        return jsonify({"patients": result})
    except Exception as e:
        return jsonify({"patients": [], "error": str(e)})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development") == "development"
    print(f"\n[HEAL+ API] Iniciando em http://localhost:{port}")
    print(f"[HEAL+ API] Debug: {debug}")
    _init_gemini()
    app.run(host="0.0.0.0", port=port, debug=debug)
