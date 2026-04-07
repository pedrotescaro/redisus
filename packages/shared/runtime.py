"""Shared runtime helpers for app entrypoints."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def ensure_project_root_on_path() -> Path:
    root_str = str(PROJECT_ROOT)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return PROJECT_ROOT


def load_project_env() -> None:
    ensure_project_root_on_path()
    load_dotenv(PROJECT_ROOT / "backend" / ".env.local", override=True)
    load_dotenv(PROJECT_ROOT / "backend" / ".env", override=True)
    load_dotenv(PROJECT_ROOT / ".env", override=True)
