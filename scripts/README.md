# Scripts

Scripts are operational helpers, not a dumping ground for generated artifacts.

## Conventions

- Put reusable logic in `src/`, `apps/`, or `packages/`; keep scripts as thin orchestration wrappers.
- Prefer `main()` functions and `if __name__ == "__main__"` guards.
- Write outputs to ignored directories such as `dataset/`, `models/`, `runs/`, or a configured external path.
- Do not require real clinical data for default execution.
- Document any required environment variables in `docs/dev/entrypoints.md` or the script header.

## Current groups

- Training: `train_*.py`, `run_training.py`, `retrain.py`.
- Dataset preparation: `medetec_scraper.py`, `prepare_yolo_dataset.py`, `preprocess_dataset.py`, `medical_augmentation.py`.
- Research/report utilities: `create_*report.py`, `update_*report.py`, `validate_*`.
- Operational launchers: `start-backend-production.ps1`, root launchers documented in `docs/dev/entrypoints.md`.

