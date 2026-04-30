from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = REPO_ROOT / "web" / "redisus-frontend"
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 5000
FRONTEND_HOST = "127.0.0.1"
FRONTEND_PORT = 3000
ANALYZER_URL = f"http://{FRONTEND_HOST}:{FRONTEND_PORT}/analyzer"
BACKEND_HEALTH_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}/health"
FRONTEND_UPSTREAM_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}/api/v1"


def _is_url_ready(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def _wait_for_url(url: str, *, timeout_seconds: float = 45.0, interval_seconds: float = 0.75) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _is_url_ready(url):
            return True
        time.sleep(interval_seconds)
    return False


def _resolve_npm_command() -> str:
    for candidate in ("npm.cmd", "npm"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError("Node.js/npm nao encontrado. Instale o Node.js para abrir o frontend Vite.")


def _popen_kwargs() -> dict[str, object]:
    kwargs: dict[str, object] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        kwargs["start_new_session"] = True
    return kwargs


def _start_backend() -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env["CLINICAL_API_REQUIRE_AUTH"] = "0"
    env["CLINICAL_API_ALLOWED_ORIGIN"] = f"http://{FRONTEND_HOST}:{FRONTEND_PORT}"
    env.setdefault("FLASK_ENV", "development")

    command = [
        sys.executable,
        "-c",
        (
            "from apps.api.app import app; "
            f"app.run(host='{BACKEND_HOST}', port={BACKEND_PORT}, debug=False, use_reloader=False)"
        ),
    ]
    return subprocess.Popen(command, cwd=str(REPO_ROOT), env=env, **_popen_kwargs())


def _start_frontend() -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env.setdefault("CLINICAL_API_URL", FRONTEND_UPSTREAM_URL)
    env.setdefault("VITE_CLINICAL_API_URL", "/api/clinical")
    env["VITE_HEAL_ANALYZER_LOCAL_MODE"] = "true"

    command = [
        _resolve_npm_command(),
        "run",
        "dev",
        "--",
        "--hostname",
        FRONTEND_HOST,
        "--port",
        str(FRONTEND_PORT),
    ]
    return subprocess.Popen(command, cwd=str(FRONTEND_DIR), env=env, **_popen_kwargs())


def launch_heal_analyzer_web() -> int:
    print("[HEAL+] Abrindo HEAL Analyzer em Vite...")

    started_backend = False
    started_frontend = False

    if not _is_url_ready(BACKEND_HEALTH_URL):
        print(f"[HEAL+] Iniciando API clinica em http://{BACKEND_HOST}:{BACKEND_PORT}")
        _start_backend()
        started_backend = True

    if not _wait_for_url(BACKEND_HEALTH_URL, timeout_seconds=45.0):
        print("[HEAL+] Nao foi possivel subir a API clinica.")
        return 1

    if not _is_url_ready(ANALYZER_URL):
        print(f"[HEAL+] Iniciando frontend em http://{FRONTEND_HOST}:{FRONTEND_PORT}")
        _start_frontend()
        started_frontend = True

    if not _wait_for_url(ANALYZER_URL, timeout_seconds=90.0):
        print("[HEAL+] O frontend nao respondeu a tempo.")
        print(f"[HEAL+] Tente abrir manualmente: {ANALYZER_URL}")
        return 1

    if started_backend:
        print("[HEAL+] API clinica pronta.")
    if started_frontend:
        print("[HEAL+] Frontend Vite pronto.")

    webbrowser.open(ANALYZER_URL)
    print(f"[HEAL+] HEAL Analyzer aberto em {ANALYZER_URL}")
    print("[HEAL+] Para voltar ao desktop legado, rode com HEAL_ANALYZER_UI=desktop.")
    return 0
