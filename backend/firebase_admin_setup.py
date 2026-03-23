# -*- coding: utf-8 -*-
"""
Firebase Admin SDK - Inicializacao centralizada para o backend HEAL+/REDISUS.
"""
import os
import json
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore, storage, auth

_app = None


def _init_firebase():
    global _app
    if _app is not None:
        return _app

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
    return firestore.client()


def get_storage_bucket():
    _init_firebase()
    bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET", "")
    return storage.bucket(bucket_name) if bucket_name else storage.bucket()


def verify_id_token(id_token: str) -> dict:
    _init_firebase()
    return auth.verify_id_token(id_token)


_init_firebase()
