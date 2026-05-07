#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run experimental OpenCV preprocessing comparisons for HEAL+ images."""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import numpy as np

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from src.processing.preprocessing_filters import (
    ensure_bgr_for_analysis,
    get_preprocessing_methods,
    iter_image_files,
    load_image_bgr,
    save_image,
)

CSV_FIELDS = [
    "image_name",
    "preprocessing_method",
    "image_resolution",
    "model_used",
    "confidence_score",
    "detected_area",
    "roi_count",
    "predicted_class",
    "processing_time_ms",
    "notes",
]

GRID_METHODS = [
    "original",
    "median",
    "gaussian",
    "equalized_color",
    "median_equalized",
    "gaussian_equalized",
    "clahe_color",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run experimental OpenCV preprocessing filters before HEAL+ image analysis.",
    )
    parser.add_argument("--input", required=True, type=Path, help="Input folder containing wound images.")
    parser.add_argument(
        "--output",
        default=Path("outputs/preprocessing_experiments"),
        type=Path,
        help="Output folder for processed images and reports.",
    )
    parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="Only save preprocessed images and grids; do not run ClinicalWoundAnalyzer.",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=None,
        help="Optional limit for quick exploratory runs.",
    )
    return parser.parse_args()


def load_analyzer(skip_ai: bool) -> tuple[Any | None, str]:
    if skip_ai:
        return None, "not_available"
    try:
        from src.processing.clinical_wound_analyzer_core import ClinicalWoundAnalyzer

        return ClinicalWoundAnalyzer(), "ClinicalWoundAnalyzer"
    except Exception as exc:
        return None, f"not_available: {exc}"


def normalize_for_grid(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def normalize_for_cv_grid(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return image.copy()


def safe_stem(path: Path) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in path.stem)


def extract_report_metrics(report: Any, model_used: str) -> dict[str, str]:
    if report is None:
        return {
            "model_used": "not_available",
            "confidence_score": "not_available",
            "detected_area": "not_available",
            "roi_count": "not_available",
            "predicted_class": "not_available",
            "processing_time_ms": "not_available",
            "notes": "ai_not_run",
        }

    roi_count: str
    if getattr(report, "rois", None):
        roi_count = str(len(report.rois))
    elif getattr(report, "roi", None):
        roi_count = "1"
    else:
        roi_count = "not_available"

    notes = "valid_wound" if getattr(report, "is_valid_wound", False) else "invalid_or_rejected"
    rejection_reason = getattr(report, "rejection_reason", "")
    if rejection_reason:
        notes = f"{notes}: {rejection_reason}"

    return {
        "model_used": model_used,
        "confidence_score": "not_available",
        "detected_area": str(getattr(report, "wound_area_px", "not_available")),
        "roi_count": roi_count,
        "predicted_class": str(getattr(report, "primary_tissue", "") or "not_available"),
        "processing_time_ms": f"{float(getattr(report, 'processing_time_ms', 0.0)):.2f}",
        "notes": notes,
    }


def run_analysis(analyzer: Any | None, image: np.ndarray, model_used: str) -> dict[str, str]:
    if analyzer is None:
        return extract_report_metrics(None, model_used)
    try:
        report = analyzer.analyze(ensure_bgr_for_analysis(image))
        return extract_report_metrics(report, model_used)
    except Exception as exc:
        return {
            "model_used": model_used,
            "confidence_score": "not_available",
            "detected_area": "not_available",
            "roi_count": "not_available",
            "predicted_class": "not_available",
            "processing_time_ms": "not_available",
            "notes": f"analysis_error: {exc}",
        }


def write_comparison_grid(
    image_name: str,
    variants: dict[str, np.ndarray],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    methods = [method for method in GRID_METHODS if method in variants]
    cols = 3
    rows = int(np.ceil(len(methods) / cols))

    if not HAS_MATPLOTLIB:
        tile_w, tile_h = 320, 260
        label_h = 36
        canvas = np.full((rows * tile_h, cols * tile_w, 3), 255, dtype=np.uint8)
        for index, method in enumerate(methods):
            row = index // cols
            col = index % cols
            tile = np.full((tile_h, tile_w, 3), 255, dtype=np.uint8)
            image = normalize_for_cv_grid(variants[method])
            resized = cv2.resize(image, (tile_w, tile_h - label_h), interpolation=cv2.INTER_AREA)
            tile[label_h:, :] = resized
            cv2.putText(tile, method, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (40, 40, 40), 2, cv2.LINE_AA)
            y0, x0 = row * tile_h, col * tile_w
            canvas[y0:y0 + tile_h, x0:x0 + tile_w] = tile
        cv2.imwrite(str(output_dir / f"{image_name}_comparison_grid.png"), canvas)
        return

    fig, axes = plt.subplots(rows, cols, figsize=(12, 4 * rows))
    axes_array = np.array(axes).reshape(-1)

    for axis, method in zip(axes_array, methods):
        axis.imshow(normalize_for_grid(variants[method]))
        axis.set_title(method)
        axis.axis("off")

    for axis in axes_array[len(methods):]:
        axis.axis("off")

    fig.tight_layout()
    fig.savefig(output_dir / f"{image_name}_comparison_grid.png", dpi=160)
    plt.close(fig)


def main() -> int:
    args = parse_args()
    input_dir = args.input
    output_dir = args.output
    reports_dir = output_dir / "reports"
    grids_dir = reports_dir / "comparison_grids"
    csv_path = reports_dir / "preprocessing_results.csv"

    if not input_dir.exists():
        raise FileNotFoundError(f"Input folder does not exist: {input_dir}")

    methods = get_preprocessing_methods()
    for method in methods:
        (output_dir / method).mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    grids_dir.mkdir(parents=True, exist_ok=True)

    image_paths = iter_image_files(input_dir)
    if args.max_images is not None:
        image_paths = image_paths[: args.max_images]

    analyzer, model_used = load_analyzer(args.skip_ai)
    rows: list[dict[str, str]] = []

    for image_path in image_paths:
        original = load_image_bgr(image_path)
        image_id = safe_stem(image_path)
        variants: dict[str, np.ndarray] = {}

        for method_name, transform in methods.items():
            start = time.perf_counter()
            processed = transform(original)
            preprocessing_time_ms = (time.perf_counter() - start) * 1000
            variants[method_name] = processed

            suffix = ".png" if processed.ndim == 2 else image_path.suffix.lower()
            output_path = output_dir / method_name / f"{image_id}_{method_name}{suffix}"
            save_image(output_path, processed)

            height, width = processed.shape[:2]
            metrics = run_analysis(analyzer, processed, model_used)
            if metrics["processing_time_ms"] == "not_available":
                metrics["processing_time_ms"] = f"{preprocessing_time_ms:.2f}"

            rows.append(
                {
                    "image_name": image_path.name,
                    "preprocessing_method": method_name,
                    "image_resolution": f"{width}x{height}",
                    **metrics,
                }
            )

        write_comparison_grid(image_id, variants, grids_dir)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Images processed: {len(image_paths)}")
    print(f"Results CSV: {csv_path}")
    print(f"Comparison grids: {grids_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
