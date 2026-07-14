"""Exporta checkpoint de segmentacao para TorchScript ou ONNX e verifica saida."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.processing.wound_segmentation_dl import MODEL_ARCHITECTURE, SmallUNet


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--format", choices=["onnx", "torchscript"], default="onnx")
    parser.add_argument("--output", default="ml/models/wound_segmentation.onnx")
    parser.add_argument("--model-card", default="ml/model_cards/wound_segmentation.md")
    parser.add_argument("--allow-non-commercial-research", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    checkpoint = Path(args.checkpoint)
    if not checkpoint.exists():
        raise SystemExit(f"Checkpoint nao encontrado: {checkpoint}")

    checkpoint_payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    license_scope = str(checkpoint_payload.get("license_scope", "unknown"))
    if "non_commercial" in license_scope and not args.allow_non_commercial_research:
        raise SystemExit(
            "Exportacao bloqueada: checkpoint restrito a pesquisa nao comercial. "
            "Use --allow-non-commercial-research somente apos revisar os termos."
        )
    model_card = Path(args.model_card)
    if not model_card.exists():
        raise SystemExit(f"Model card obrigatorio nao encontrado: {model_card}")

    architecture = checkpoint_payload.get("architecture", checkpoint_payload.get("model"))
    if architecture not in {MODEL_ARCHITECTURE, "SmallUNet"}:
        raise SystemExit(f"Arquitetura nao suportada: {architecture}")
    base_channels = int(checkpoint_payload.get("base_channels", 16 if architecture == MODEL_ARCHITECTURE else 32))
    image_size = int(checkpoint_payload.get("training_args", {}).get("image_size", 256))
    model = SmallUNet(base_channels=base_channels)
    model.load_state_dict(checkpoint_payload["model_state_dict"])
    model.eval()
    example = torch.zeros(1, 3, image_size, image_size, dtype=torch.float32)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "torchscript":
        exported = torch.jit.trace(model, example)
        exported.save(str(output))
        with torch.inference_mode():
            max_abs_error = float((exported(example) - model(example)).abs().max().item())
    else:
        torch.onnx.export(
            model,
            example,
            str(output),
            input_names=["image"],
            output_names=["logits"],
            dynamic_axes={"image": {0: "batch"}, "logits": {0: "batch"}},
            opset_version=17,
        )
        max_abs_error = None

    metadata = {
        "checkpoint": str(checkpoint),
        "format": args.format,
        "output": str(output),
        "bytes": output.stat().st_size,
        "architecture": MODEL_ARCHITECTURE,
        "base_channels": base_channels,
        "image_size": image_size,
        "decision_threshold": checkpoint_payload.get("decision_threshold", 0.5),
        "model_version": checkpoint_payload.get("model_version"),
        "clinical_status": checkpoint_payload.get("clinical_status"),
        "license_scope": license_scope,
        "model_card": str(model_card),
        "verification_max_abs_error": max_abs_error,
    }
    metadata_path = output.with_suffix(output.suffix + ".json")
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
