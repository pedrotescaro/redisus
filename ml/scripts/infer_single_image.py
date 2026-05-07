"""Run single-image segmentation inference with a validated exported model.

This script intentionally refuses to run without an explicit model path. It is
for offline validation, not for clinical diagnosis.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output-mask", default="ml/outputs/inference_mask.png")
    parser.add_argument("--threshold", type=float, default=0.5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image = Path(args.image)
    model = Path(args.model)
    if not image.exists():
        raise SystemExit(f"Imagem nao encontrada: {image}")
    if not model.exists():
        raise SystemExit(f"Modelo nao encontrado: {model}")

    plan = {
        "image": str(image),
        "model": str(model),
        "output_mask": args.output_mask,
        "threshold": args.threshold,
        "status": "scaffold_only",
        "disclaimer": "Inferencia offline assistiva; nao usar como diagnostico."
    }
    print(json.dumps(plan, indent=2))
    raise SystemExit("Implementar backend ONNX/TorchScript apenas apos validacao formal do modelo.")


if __name__ == "__main__":
    main()
