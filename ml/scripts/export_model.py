"""Export a validated segmentation model for inference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--format", choices=["onnx", "torchscript"], default="onnx")
    parser.add_argument("--output", default="ml/models/wound_segmentation.onnx")
    parser.add_argument("--model-card", default="ml/model_cards/wound_segmentation.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    checkpoint = Path(args.checkpoint)
    if not checkpoint.exists():
        raise SystemExit(f"Checkpoint nao encontrado: {checkpoint}")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    plan = {
        "checkpoint": str(checkpoint),
        "format": args.format,
        "output": str(output),
        "requires": "Implementar exportacao apos aprovacao do modelo e model card.",
        "model_card": args.model_card
    }
    print(json.dumps(plan, indent=2))
    raise SystemExit("Export scaffold ready; nao exportar modelo sem validacao e model card aprovado.")


if __name__ == "__main__":
    main()
