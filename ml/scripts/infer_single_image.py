"""Executa inferencia offline de segmentacao com rastreabilidade e abstencao."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output-mask", default="ml/outputs/inference_mask.png")
    parser.add_argument("--output-metadata", default="")
    parser.add_argument("--roi-mask", default="")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--allow-non-commercial-research", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image = Path(args.image)
    model = Path(args.model)
    if not image.exists():
        raise SystemExit(f"Imagem nao encontrada: {image}")
    if not model.exists():
        raise SystemExit(f"Modelo nao encontrado: {model}")

    import cv2

    from src.processing.wound_segmentation_dl import WoundSegmentationPredictor

    source = cv2.imread(str(image), cv2.IMREAD_COLOR)
    if source is None:
        raise SystemExit(f"Nao foi possivel decodificar a imagem: {image}")
    roi = None
    if args.roi_mask:
        roi_path = Path(args.roi_mask)
        roi = cv2.imread(str(roi_path), cv2.IMREAD_GRAYSCALE)
        if roi is None:
            raise SystemExit(f"Nao foi possivel decodificar a ROI: {roi_path}")

    predictor = WoundSegmentationPredictor(
        model,
        device=args.device,
        allow_non_commercial_research=args.allow_non_commercial_research,
    )
    prediction = predictor.predict(source, roi_mask=roi)
    output_mask = Path(args.output_mask)
    output_mask.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_mask), prediction.mask):
        raise SystemExit(f"Falha ao salvar mascara em {output_mask}")
    metadata_path = Path(args.output_metadata) if args.output_metadata else output_mask.with_suffix(".json")
    metadata = {
        **prediction.metadata(),
        "image": str(image),
        "checkpoint": str(model),
        "output_mask": str(output_mask),
        "roi_mask": str(args.roi_mask) if args.roi_mask else None,
        "disclaimer": "Resultado experimental assistivo; nao usar como diagnostico autonomo.",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
