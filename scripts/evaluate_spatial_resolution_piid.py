from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.processing.roi_segmentation import ROISegmenter
from src.processing.tissue_analyzer import TissueAnalyzerCV
from src.processing.wound_detector_cv import DetectionMethod, WoundDetectorCV


DEFAULT_RESOLUTIONS = [224, 192, 160, 128, 112, 96, 80, 64, 48, 32, 24, 16]
DEFAULT_CRITERIA = {
    "roi_dice_mean_min": 0.95,
    "tissue_mae_pp_max": 1.0,
    "dominant_tissue_agreement_min": 0.98,
    "health_score_abs_delta_max": 1.5,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate how synthetic spatial-resolution degradation affects the "
            "classical chronic-wound pipeline on the PIID dataset."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "dataset" / "piid" / "manifests" / "piid_lp_split.json",
        help="Path to the PIID split manifest.",
    )
    parser.add_argument(
        "--split",
        choices=["train", "val", "test"],
        default="test",
        help="Manifest split to evaluate.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "output" / "reports" / "piid_spatial_resolution_experiment.json",
        help="Where to save the JSON summary.",
    )
    parser.add_argument(
        "--resolutions",
        type=int,
        nargs="+",
        default=DEFAULT_RESOLUTIONS,
        help="Square resolutions to simulate before upsampling back to the native size.",
    )
    return parser.parse_args()


def degrade_image(image: np.ndarray, target_px: int) -> np.ndarray:
    height, width = image.shape[:2]
    if target_px >= min(height, width):
        return image.copy()

    downsampled = cv2.resize(image, (target_px, target_px), interpolation=cv2.INTER_AREA)
    return cv2.resize(downsampled, (width, height), interpolation=cv2.INTER_LINEAR)


def dice_score(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    binary_a = mask_a > 0
    binary_b = mask_b > 0
    intersection = np.logical_and(binary_a, binary_b).sum()
    total = binary_a.sum() + binary_b.sum()
    return 1.0 if total == 0 else float((2.0 * intersection) / total)


def iou_score(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    binary_a = mask_a > 0
    binary_b = mask_b > 0
    intersection = np.logical_and(binary_a, binary_b).sum()
    union = np.logical_or(binary_a, binary_b).sum()
    return 1.0 if union == 0 else float(intersection / union)


def summarize(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "mean": float(array.mean()),
        "std": float(array.std()),
        "median": float(np.median(array)),
        "p10": float(np.percentile(array, 10)),
        "p90": float(np.percentile(array, 90)),
    }


def build_wound_mask(
    image_bgr: np.ndarray,
    detector: WoundDetectorCV,
    roi_segmenter: ROISegmenter,
) -> np.ndarray:
    detections = detector.detect(image_bgr)
    wound_mask = roi_segmenter.create_wound_roi_mask(image_bgr, detections)
    wound_mask = roi_segmenter.exclude_surgical_background(image_bgr, wound_mask)
    background_mask = roi_segmenter.create_background_mask_spatial(image_bgr, wound_mask)
    return cv2.bitwise_and(wound_mask, cv2.bitwise_not(background_mask))


def find_recommended_resolution(
    results_by_resolution: dict[str, dict[str, object]],
    criteria: dict[str, float],
) -> int | None:
    valid: list[int] = []
    for resolution_str, metrics in results_by_resolution.items():
        if (
            metrics["roi_dice"]["mean"] >= criteria["roi_dice_mean_min"]
            and metrics["tissue_mae_pp"]["mean"] <= criteria["tissue_mae_pp_max"]
            and metrics["dominant_tissue_agreement"]["mean"] >= criteria["dominant_tissue_agreement_min"]
            and metrics["health_score_abs_delta"]["mean"] <= criteria["health_score_abs_delta_max"]
        ):
            valid.append(int(resolution_str))
    return min(valid) if valid else None


def main() -> int:
    args = parse_args()
    logger.remove()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    entries = manifest["splits"][args.split]

    detector = WoundDetectorCV(
        method=DetectionMethod.TEXTURE_PRIORITY,
        enable_false_positive_filter=False,
    )
    roi_segmenter = ROISegmenter()
    tissue_analyzer = TissueAnalyzerCV()

    baseline: list[dict[str, object]] = []
    for entry in entries:
        image_path = Path(entry["path"])
        image = cv2.imread(str(image_path))
        if image is None:
            raise FileNotFoundError(f"Could not read image: {image_path}")

        wound_mask = build_wound_mask(image, detector, roi_segmenter)
        tissue_result = tissue_analyzer.analyze(image, wound_mask)

        baseline.append(
            {
                "path": str(image_path),
                "stage_code": entry["stage_code"],
                "image": image,
                "mask": wound_mask,
                "tissue_percentages": {
                    key: float(value) for key, value in tissue_result.tissue_percentages.items()
                },
                "dominant_tissue": tissue_result.dominant_tissue,
                "health_score": float(tissue_result.health_score),
                "wound_area_pixels": int(tissue_result.wound_area_pixels),
            }
        )

    results: dict[str, object] = {
        "dataset": manifest["dataset_name"],
        "source_root": manifest["source_root"],
        "split": args.split,
        "n_images": len(entries),
        "baseline_resolution_px": int(baseline[0]["image"].shape[0]) if baseline else None,
        "criteria": DEFAULT_CRITERIA,
        "resolutions": {},
    }

    for resolution in args.resolutions:
        roi_dice_values: list[float] = []
        roi_iou_values: list[float] = []
        tissue_mae_values: list[float] = []
        dominant_values: list[float] = []
        health_delta_values: list[float] = []
        wound_area_error_values: list[float] = []
        per_stage: dict[str, dict[str, object]] = {}

        for item in baseline:
            degraded = degrade_image(item["image"], resolution)
            wound_mask = build_wound_mask(degraded, detector, roi_segmenter)
            tissue_result = tissue_analyzer.analyze(degraded, wound_mask)

            roi_dice = dice_score(item["mask"], wound_mask)
            roi_iou = iou_score(item["mask"], wound_mask)
            all_tissues = sorted(
                set(item["tissue_percentages"].keys()) | set(tissue_result.tissue_percentages.keys())
            )
            tissue_mae = sum(
                abs(
                    float(item["tissue_percentages"].get(tissue, 0.0))
                    - float(tissue_result.tissue_percentages.get(tissue, 0.0))
                )
                for tissue in all_tissues
            ) / max(len(all_tissues), 1)
            dominant_agreement = 1.0 if item["dominant_tissue"] == tissue_result.dominant_tissue else 0.0
            health_delta = abs(float(item["health_score"]) - float(tissue_result.health_score))
            wound_area_error = abs(
                int(item["wound_area_pixels"]) - int(tissue_result.wound_area_pixels)
            ) / max(int(item["wound_area_pixels"]), 1)

            roi_dice_values.append(roi_dice)
            roi_iou_values.append(roi_iou)
            tissue_mae_values.append(tissue_mae)
            dominant_values.append(dominant_agreement)
            health_delta_values.append(health_delta)
            wound_area_error_values.append(wound_area_error)

            stage_stats = per_stage.setdefault(
                str(item["stage_code"]),
                {
                    "count": 0,
                    "roi_dice": [],
                    "tissue_mae_pp": [],
                    "dominant_tissue_agreement": [],
                },
            )
            stage_stats["count"] += 1
            stage_stats["roi_dice"].append(roi_dice)
            stage_stats["tissue_mae_pp"].append(tissue_mae)
            stage_stats["dominant_tissue_agreement"].append(dominant_agreement)

        results["resolutions"][str(resolution)] = {
            "roi_dice": summarize(roi_dice_values),
            "roi_iou": summarize(roi_iou_values),
            "tissue_mae_pp": summarize(tissue_mae_values),
            "dominant_tissue_agreement": summarize(dominant_values),
            "health_score_abs_delta": summarize(health_delta_values),
            "wound_area_relative_error": summarize(wound_area_error_values),
            "per_stage": {
                stage_code: {
                    "count": int(stage_values["count"]),
                    "roi_dice_mean": float(np.mean(stage_values["roi_dice"])),
                    "tissue_mae_pp_mean": float(np.mean(stage_values["tissue_mae_pp"])),
                    "dominant_tissue_agreement_mean": float(
                        np.mean(stage_values["dominant_tissue_agreement"])
                    ),
                }
                for stage_code, stage_values in sorted(per_stage.items())
            },
        }

    results["recommended_min_resolution_px"] = find_recommended_resolution(
        results["resolutions"],
        DEFAULT_CRITERIA,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Saved experiment summary to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
