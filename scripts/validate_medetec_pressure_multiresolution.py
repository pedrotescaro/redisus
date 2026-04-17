from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.diagnosis.pressure_injury_stage_classifier import PressureInjuryStageClassifier
from src.processing.clinical_wound_analyzer_core import ClinicalWoundAnalyzer


PRESSURE_FOLDERS = ("pressure_ulcers_1", "pressure_ulcers_2")
TESTED_SIZES = (512, 448, 320, 256, 224, 192, 160)


def _load_metadata(metadata_path: Path) -> dict[str, Any]:
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _collect_samples(metadata: dict[str, Any], dataset_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    skipped_intro = 0
    size_counter: Counter[tuple[int, int]] = Counter()
    min_width = 10**9
    min_height = 10**9
    max_width = 0
    max_height = 0

    for category in metadata.get("categories") or []:
        folder = str(category.get("folder") or "")
        if folder not in PRESSURE_FOLDERS:
            continue
        for image_meta in category.get("images") or []:
            source_url = str(image_meta.get("url") or "")
            if "introslide" in source_url.lower():
                skipped_intro += 1
                continue

            image_path = dataset_dir / folder / str(image_meta["filename"])
            if not image_path.exists():
                continue

            with Image.open(image_path) as image:
                width, height = image.size
            size_counter[(width, height)] += 1
            min_width = min(min_width, width)
            min_height = min(min_height, height)
            max_width = max(max_width, width)
            max_height = max(max_height, height)

            samples.append(
                {
                    "path": str(image_path),
                    "filename": image_path.name,
                    "folder": folder,
                    "source_url": source_url,
                    "native_width": width,
                    "native_height": height,
                    "native_pixels": width * height,
                }
            )

    top_sizes = [
        {"width": width, "height": height, "count": count}
        for (width, height), count in size_counter.most_common(10)
    ]
    stats = {
        "folders": list(PRESSURE_FOLDERS),
        "excluded_intro_slides": skipped_intro,
        "total_images": len(samples),
        "unique_sizes": len(size_counter),
        "top_sizes": top_sizes,
        "min_size": {"width": min_width if samples else 0, "height": min_height if samples else 0},
        "max_size": {"width": max_width, "height": max_height},
    }
    return samples, stats


def _analyze_variant(
    analyzer: ClinicalWoundAnalyzer,
    stage_classifier: PressureInjuryStageClassifier,
    image,
) -> dict[str, Any]:
    started = time.time()
    report = analyzer.analyze(image)
    elapsed_ms = (time.time() - started) * 1000
    stage_prediction = stage_classifier.predict(
        image,
        evaluation_context={"wound_area_cm2": 0.0, "pain_score": 0.0},
    ).to_dict()

    height, width = image.shape[:2]
    total_pixels = max(1, width * height)
    wound_area_px = int(getattr(report, "wound_area_px", 0) or 0)

    return {
        "width": width,
        "height": height,
        "total_pixels": total_pixels,
        "analyzer_success": True,
        "analyzer_is_valid_wound": bool(getattr(report, "is_valid_wound", False)),
        "analyzer_rejection_reason": getattr(report, "rejection_reason", "") or "",
        "analyzer_primary_tissue": getattr(report, "primary_tissue", "") or "",
        "analyzer_wound_area_px": wound_area_px,
        "analyzer_wound_fraction": round(wound_area_px / total_pixels, 6),
        "analyzer_health_score": round(float(getattr(report, "health_score", 0.0) or 0.0), 4),
        "analyzer_processing_time_ms": round(
            float(getattr(report, "processing_time_ms", 0.0) or elapsed_ms),
            2,
        ),
        "predicted_stage": stage_prediction["stage_code"],
        "predicted_stage_confidence": stage_prediction["confidence"],
        "stage_source": stage_prediction["source"],
        "stage_model_available": stage_prediction["model_available"],
        "stage_needs_expert_review": stage_prediction["needs_expert_review"],
    }


def _variant_error_payload(image, exc: Exception) -> dict[str, Any]:
    height, width = image.shape[:2]
    return {
        "width": width,
        "height": height,
        "total_pixels": width * height,
        "analyzer_success": False,
        "error": f"{type(exc).__name__}: {exc}",
    }


def _summarize_variant(records: list[dict[str, Any]], key: str) -> dict[str, Any]:
    entries = [record["variants"][key] for record in records]
    total = len(entries)
    success = [entry for entry in entries if entry.get("analyzer_success")]
    valid = [entry for entry in success if entry.get("analyzer_is_valid_wound")]

    processing_times = [float(entry.get("analyzer_processing_time_ms") or 0.0) for entry in success]
    wound_fractions = [float(entry.get("analyzer_wound_fraction") or 0.0) for entry in success]
    health_scores = [float(entry.get("analyzer_health_score") or 0.0) for entry in success]
    tissue_counts = Counter(
        str(entry.get("analyzer_primary_tissue") or "Sem tecido")
        for entry in valid
    )
    stage_counts = Counter(
        str(entry.get("predicted_stage") or "unknown")
        for entry in success
    )

    return {
        "total_images": total,
        "analyzer_success": len(success),
        "analyzer_success_rate": round(len(success) / max(1, total), 4),
        "analyzer_valid_wound_rate": round(len(valid) / max(1, len(success)), 4),
        "analyzer_avg_processing_time_ms": round(sum(processing_times) / max(1, len(processing_times)), 2),
        "avg_wound_fraction": round(sum(wound_fractions) / max(1, len(wound_fractions)), 6),
        "avg_health_score": round(sum(health_scores) / max(1, len(health_scores)), 4),
        "primary_tissue_counts": dict(sorted(tissue_counts.items())),
        "predicted_stage_counts": dict(sorted(stage_counts.items())),
    }


def _summarize_vs_native(records: list[dict[str, Any]], key: str) -> dict[str, Any]:
    total = len(records)
    valid_agreement = 0
    tissue_comparable = 0
    tissue_agreement = 0
    stage_agreement = 0
    wound_fraction_deltas: list[float] = []
    health_deltas: list[float] = []
    pixel_ratios: list[float] = []

    valid_changed = 0
    tissue_changed = 0
    stage_changed = 0

    for record in records:
        native = record["variants"]["native"]
        variant = record["variants"][key]

        native_valid = bool(native.get("analyzer_is_valid_wound"))
        variant_valid = bool(variant.get("analyzer_is_valid_wound"))
        if native_valid == variant_valid:
            valid_agreement += 1
        else:
            valid_changed += 1

        native_tissue = str(native.get("analyzer_primary_tissue") or "")
        variant_tissue = str(variant.get("analyzer_primary_tissue") or "")
        if native_valid and variant_valid and native_tissue and variant_tissue:
            tissue_comparable += 1
            if native_tissue == variant_tissue:
                tissue_agreement += 1
            else:
                tissue_changed += 1

        native_stage = str(native.get("predicted_stage") or "")
        variant_stage = str(variant.get("predicted_stage") or "")
        if native_stage == variant_stage:
            stage_agreement += 1
        else:
            stage_changed += 1

        wound_fraction_deltas.append(
            abs(float(native.get("analyzer_wound_fraction") or 0.0) - float(variant.get("analyzer_wound_fraction") or 0.0))
        )
        health_deltas.append(
            abs(float(native.get("analyzer_health_score") or 0.0) - float(variant.get("analyzer_health_score") or 0.0))
        )
        pixel_ratios.append(
            float(variant.get("total_pixels") or 0.0) / max(1.0, float(native.get("total_pixels") or 1.0))
        )

    return {
        "total_pairs": total,
        "valid_wound_agreement_rate": round(valid_agreement / max(1, total), 4),
        "primary_tissue_agreement_rate": round(tissue_agreement / max(1, tissue_comparable), 4),
        "primary_tissue_comparable_pairs": tissue_comparable,
        "predicted_stage_agreement_rate": round(stage_agreement / max(1, total), 4),
        "avg_abs_wound_fraction_delta": round(sum(wound_fraction_deltas) / max(1, len(wound_fraction_deltas)), 6),
        "avg_abs_health_score_delta": round(sum(health_deltas) / max(1, len(health_deltas)), 4),
        "avg_pixel_retention_ratio": round(sum(pixel_ratios) / max(1, len(pixel_ratios)), 4),
        "valid_changed_count": valid_changed,
        "primary_tissue_changed_count": tissue_changed,
        "predicted_stage_changed_count": stage_changed,
    }


def validate(
    *,
    dataset_dir: Path,
    metadata_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    metadata = _load_metadata(metadata_path)
    samples, dataset_stats = _collect_samples(metadata, dataset_dir)

    analyzer = ClinicalWoundAnalyzer()
    stage_classifier = PressureInjuryStageClassifier()
    records: list[dict[str, Any]] = []

    for index, sample in enumerate(samples, start=1):
        image_path = Path(sample["path"])
        image = cv2.imread(str(image_path))
        record: dict[str, Any] = {
            "index": index,
            **sample,
            "variants": {},
        }
        if image is None:
            for key in ("native", *[f"resized_{size}" for size in TESTED_SIZES]):
                record["variants"][key] = {"analyzer_success": False, "error": "image_unreadable"}
            records.append(record)
            continue

        try:
            record["variants"]["native"] = _analyze_variant(analyzer, stage_classifier, image)
        except Exception as exc:
            record["variants"]["native"] = _variant_error_payload(image, exc)

        for size in TESTED_SIZES:
            resized = cv2.resize(image, (size, size), interpolation=cv2.INTER_AREA)
            key = f"resized_{size}"
            try:
                record["variants"][key] = _analyze_variant(analyzer, stage_classifier, resized)
            except Exception as exc:
                record["variants"][key] = _variant_error_payload(resized, exc)
        records.append(record)

    resolutions = {
        "native": _summarize_variant(records, "native"),
    }
    for size in TESTED_SIZES:
        key = f"resized_{size}"
        resolutions[key] = _summarize_variant(records, key)

    vs_native = {}
    for size in TESTED_SIZES:
        key = f"resized_{size}"
        vs_native[key] = _summarize_vs_native(records, key)

    payload = {
        "dataset": {
            "name": "Medetec Pressure Ulcers",
            "source_root": str(dataset_dir),
            "metadata_path": str(metadata_path),
            "analysis_mode": "native_vs_multiple_square_resizes",
            "tested_sizes": list(TESTED_SIZES),
            **dataset_stats,
        },
        "models": {
            "heal_analyzer": "ClinicalWoundAnalyzer headless",
            "pressure_stage_classifier_available": stage_classifier.available,
            "pressure_stage_classifier_version": stage_classifier.model_version,
        },
        "summary": {
            "resolutions": resolutions,
            "vs_native": vs_native,
        },
        "records": records,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Valida a Medetec de lesão por pressão em múltiplas resoluções quadradas versus a imagem nativa."
    )
    parser.add_argument("--dataset-dir", default="dataset/medetec")
    parser.add_argument("--metadata", default="dataset/medetec/metadata.json")
    parser.add_argument("--output", default="output/validation/medetec_pressure_multiresolution_validation.json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = validate(
        dataset_dir=Path(args.dataset_dir),
        metadata_path=Path(args.metadata),
        output_path=Path(args.output),
    )
    print(json.dumps({"summary": payload["summary"], "output": args.output}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
