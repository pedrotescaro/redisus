# Entrypoints and execution surface

This document defines the supported execution surface while the repository is being modularized. It does not remove legacy scripts; it makes ownership explicit so future PRs can move behavior safely.

## Official entrypoints

| Entrypoint | Purpose | Recommended command | Status |
| --- | --- | --- | --- |
| `apps/api/run.py` | Clinical/API backend wrapper | `python -m apps.api.run` | preferred for API work |
| `heal_web_launcher.py` | Local full-stack launcher for backend and Next.js frontend | `python heal_web_launcher.py` | preferred for local demo |
| `heal_platform.py` | Unified HEAL/REDISUS platform launcher | `python heal_platform.py --mode status` | supported legacy |
| `main.py` | Original integrated wound analysis pipeline | `python main.py --mode demo` | supported legacy |
| `realtime_app.py` | Realtime OpenCV desktop-style pipeline | `python realtime_app.py --mode demo` | supported legacy |
| `retrain.py` | Wrapper for improved training script | `python retrain.py --fast` | training utility |

## Script categories

| Category | Directory or files | Rule |
| --- | --- | --- |
| CI and repository checks | `scripts/ci/` when present | Must be fast, deterministic, and dependency-light |
| Training | `scripts/train_*.py`, `scripts/run_training.py`, `retrain.py` | Must not assume tracked model weights or datasets |
| Dataset preparation | `scripts/prepare_*`, `scripts/preprocess_*`, `scripts/*scraper*` | Must write outputs to ignored paths or external storage |
| Reports and research utilities | `scripts/*report*`, `docs/research/` | Prefer source formats over generated binaries |
| Production ops | `scripts/start-backend-production.ps1` | Must document required environment variables |

## Refactor rules

- Keep root wrappers until a replacement command exists and is documented.
- Move shared path/env setup into `packages.shared.runtime`.
- Keep scripts importable when possible, with side effects inside `main()`.
- Do not commit generated outputs from scripts.
- Add smoke tests before changing behavior of any official entrypoint.

