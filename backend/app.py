# -*- coding: utf-8 -*-
"""
Compatibilidade legada para o backend Flask.

O backend oficial agora vive em `apps/api/app.py`.
Este arquivo permanece apenas para evitar quebra de comandos antigos.
"""

import os

from apps.api.app import app, create_app

__all__ = ["app", "create_app"]


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development").lower() == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
