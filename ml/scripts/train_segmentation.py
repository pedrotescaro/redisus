"""Training entrypoint for wound-vs-background segmentation.

Install the ML stack in a separate environment before running:
torch, torchvision, segmentation-models-pytorch, albumentations, numpy, pillow.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="ml/configs/segmentation_baseline.yaml")
    parser.add_argument("--train-manifest", default="ml/datasets/train.jsonl")
    parser.add_argument("--val-manifest", default="ml/datasets/val.jsonl")
    parser.add_argument("--output-dir", default="ml/outputs/segmentation_baseline")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def count_manifest(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "config": args.config,
        "train_records": count_manifest(Path(args.train_manifest)),
        "val_records": count_manifest(Path(args.val_manifest)),
        "output_dir": str(output_dir),
        "status": "dry_run" if args.dry_run else "training_requires_ml_dependencies"
    }
    (output_dir / "training_plan.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

    if args.dry_run:
        return

    raise SystemExit(
        "Training scaffold ready. Add the project-approved PyTorch training loop after dataset/license review."
    )


if __name__ == "__main__":
    main()
