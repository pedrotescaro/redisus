"""Evaluate binary wound segmentation masks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", required=True, help="Directory with binary reference masks.")
    parser.add_argument("--predictions", required=True, help="Directory with predicted masks with matching filenames.")
    parser.add_argument("--output", default="ml/outputs/segmentation_metrics.json")
    return parser.parse_args()


def safe_div(num: float, den: float) -> float:
    return float(num / den) if den else 0.0


def main() -> None:
    args = parse_args()
    try:
        from PIL import Image
        import numpy as np
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"Pillow e numpy sao necessarios para avaliar: {exc}") from exc

    gt_root = Path(args.ground_truth)
    pred_root = Path(args.predictions)
    totals = {"tp": 0, "fp": 0, "tn": 0, "fn": 0, "matched": 0, "missing": 0}

    for gt_path in gt_root.rglob("*"):
        if not gt_path.is_file() or gt_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
            continue
        pred_path = pred_root / gt_path.relative_to(gt_root)
        if not pred_path.exists():
            totals["missing"] += 1
            continue
        with Image.open(gt_path) as gt_image, Image.open(pred_path) as pred_image:
            gt = np.asarray(gt_image.convert("L")) > 0
            pred = np.asarray(pred_image.resize(gt_image.size).convert("L")) > 0
            totals["tp"] += int((gt & pred).sum())
            totals["fp"] += int((~gt & pred).sum())
            totals["tn"] += int((~gt & ~pred).sum())
            totals["fn"] += int((gt & ~pred).sum())
            totals["matched"] += 1

    tp = totals["tp"]
    fp = totals["fp"]
    tn = totals["tn"]
    fn = totals["fn"]
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    metrics = {
        **totals,
        "dice": safe_div(2 * tp, 2 * tp + fp + fn),
        "iou": safe_div(tp, tp + fp + fn),
        "precision": precision,
        "recall": recall,
        "f1": safe_div(2 * precision * recall, precision + recall),
        "false_positive_rate": safe_div(fp, fp + tn),
        "false_negative_rate": safe_div(fn, fn + tp)
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
