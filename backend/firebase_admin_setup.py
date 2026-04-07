# -*- coding: utf-8 -*-
"""
Firebase Admin SDK - Inicializacao centralizada para o backend HEAL+/REDISUS.
"""
import os
import json
from pathlib import Path

try:
    import firebase_admin
    from firebase_admin import auth, credentials, firestore, storage

    _FIREBASE_AVAILABLE = True
except Exception:
    firebase_admin = None
    credentials = None
    firestore = None
    storage = None
    auth = None
    _FIREBASE_AVAILABLE = False

_app = None


def _init_firebase():
    global _app
    if _app is not None:
        return _app

    if not _FIREBASE_AVAILABLE:
        print("[Firebase Admin] [!] firebase_admin nao instalado - integracoes Firebase indisponiveis.")
        return None

    cred = None
    sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    sa_file = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE")

    if sa_json:
        try:
            cred = credentials.Certificate(json.loads(sa_json))
            print("[Firebase Admin] Credenciais carregadas de FIREBASE_SERVICE_ACCOUNT_JSON")
        except Exception as e:
            print(f"[Firebase Admin] Erro ao parsear FIREBASE_SERVICE_ACCOUNT_JSON: {e}")

    if cred is None and sa_file:
        sa_path = Path(sa_file)
        if sa_path.exists():
            cred = credentials.Certificate(str(sa_path))
            print(f"[Firebase Admin] Credenciais carregadas de {sa_path.name}")
        else:
            print(f"[Firebase Admin] Arquivo nao encontrado: {sa_file}")

    if cred is None:
        gac = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if gac and Path(gac).exists():
            cred = credentials.Certificate(gac)
            print("[Firebase Admin] Credenciais carregadas de GOOGLE_APPLICATION_CREDENTIALS")

    if cred is None:
        print("[Firebase Admin] [!] Nenhuma credencial encontrada - operacoes Firebase falharao.")
        print("[Firebase Admin] Configure FIREBASE_SERVICE_ACCOUNT_FILE ou FIREBASE_SERVICE_ACCOUNT_JSON")
        try:
            _app = firebase_admin.initialize_app()
        except Exception:
            _app = None
        return _app

    storage_bucket = os.getenv("FIREBASE_STORAGE_BUCKET", "")
    options = {}
    if storage_bucket:
        options["storageBucket"] = storage_bucket

    _app = firebase_admin.initialize_app(cred, options)
    print(f"[Firebase Admin] [OK] Inicializado - Projeto: {_app.project_id}")
    return _app


def get_firestore_db():
    _init_firebase()
    if not _FIREBASE_AVAILABLE or _app is None:
        raise RuntimeError("Firebase Admin indisponivel")
    return firestore.client()


def get_storage_bucket():
    _init_firebase()
    if not _FIREBASE_AVAILABLE or _app is None:
        raise RuntimeError("Firebase Admin indisponivel")
    bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET", "")
    return storage.bucket(bucket_name) if bucket_name else storage.bucket()


def verify_id_token(id_token: str) -> dict:
    _init_firebase()
    if not _FIREBASE_AVAILABLE or _app is None:
        raise RuntimeError("Firebase Admin indisponivel")
    return auth.verify_id_token(id_token)


def is_firebase_ready() -> bool:
    return bool(_FIREBASE_AVAILABLE and _init_firebase() is not None)


_init_firebase()
