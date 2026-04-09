from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import cv2

from src.diagnosis.pressure_injury_stage_classifier import (
    PRESSURE_STAGE_CODES,
    PressureInjuryStageClassifier,
)
from src.processing.clinical_wound_analyzer_core import ClinicalWoundAnalyzer
from src.training.pressure_injury_dataset import build_pressure_injury_manifest


def _load_manifest(path: Path, dataset_dir: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return build_pressure_injury_manifest(dataset_dir)


def _select_samples(
    manifest: dict[str, Any],
    *,
    split: str,
    samples_per_stage: int,
    seed: int,
) -> list[dict[str, Any]]:
    samples = list((manifest.get("splits") or {}).get(split) or [])
    if not samples:
        raise ValueError(f"Manifesto sem amostras no split '{split}'.")
    if samples_per_stage <= 0:
        return samples

    rng = random.Random(seed)
    selected: list[dict[str, Any]] = []
    for stage_code in PRESSURE_STAGE_CODES:
        stage_samples = [sample for sample in samples if sample.get("stage_code") == stage_code]
        rng.shuffle(stage_samples)
        selected.extend(stage_samples[:samples_per_stage])
    rng.shuffle(selected)
    return selected


def _empty_confusion() -> dict[str, dict[str, int]]:
    return {
        true_stage: {pred_stage: 0 for pred_stage in PRESSURE_STAGE_CODES}
        for true_stage in PRESSURE_STAGE_CODES
    }


def _summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    analyzer_success = [record for record in records if record.get("analyzer_success")]
    analyzer_valid = [record for record in analyzer_success if record.get("analyzer_is_valid_wound")]
    stage_correct = [
        record
        for record in records
        if record.get("predicted_stage") == record.get("true_stage")
    ]
    confusion = _empty_confusion()
    per_stage: dict[str, dict[str, Any]] = {}
    for stage_code in PRESSURE_STAGE_CODES:
        stage_records = [record for record in records if record.get("true_stage") == stage_code]
        correct = [record for record in stage_records if record.get("predicted_stage") == stage_code]
        per_stage[stage_code] = {
            "total": len(stage_records),
            "correct": len(correct),
            "accuracy": round(len(correct) / max(1, len(stage_records)), 4),
        }
    for record in records:
        true_stage = str(record.get("true_stage") or "")
        predicted_stage = str(record.get("predicted_stage") or "")
        if true_stage in confusion and predicted_stage in confusion[true_stage]:
            confusion[true_stage][predicted_stage] += 1

    processing_times = [
        float(record.get("analyzer_processing_time_ms") or 0.0)
        for record in analyzer_success
    ]
    return {
        "total_images": total,
        "analyzer_success": len(analyzer_success),
        "analyzer_success_rate": round(len(analyzer_success) / max(1, total), 4),
        "analyzer_valid_wound_rate": round(len(analyzer_valid) / max(1, len(analyzer_success)), 4),
        "analyzer_avg_processing_time_ms": round(sum(processing_times) / max(1, len(processing_times)), 2),
        "pressure_stage_accuracy": round(len(stage_correct) / max(1, total), 4),
        "pressure_stage_per_stage": per_stage,
        "pressure_stage_confusion": confusion,
    }


def validate(
    *,
    dataset_dir: Path,
    manifest_path: Path,
    output_path: Path,
    split: str,
    samples_per_stage: int,
    seed: int,
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path, dataset_dir)
    samples = _select_samples(
        manifest,
        split=split,
        samples_per_stage=samples_per_stage,
        seed=seed,
    )
    analyzer = ClinicalWoundAnalyzer()
    stage_classifier = PressureInjuryStageClassifier()
    records: list[dict[str, Any]] = []

    for index, sample in enumerate(samples, start=1):
        image_path = Path(str(sample["path"]))
        image = cv2.imread(str(image_path))
        record: dict[str, Any] = {
            "index": index,
            "path": str(image_path),
            "filename": image_path.name,
            "true_stage": sample.get("stage_code"),
        }
        if image is None:
            record.update(
                {
                    "analyzer_success": False,
                    "error": "image_unreadable",
                }
            )
            records.append(record)
            continue

        started = time.time()
        try:
            report = analyzer.analyze(image)
            elapsed_ms = (time.time() - started) * 1000
            record.update(
                {
                    "analyzer_success": True,
                    "analyzer_is_valid_wound": bool(getattr(report, "is_valid_wound", False)),
                    "analyzer_rejection_reason": getattr(report, "rejection_reason", "") or "",
                    "analyzer_primary_tissue": getattr(report, "primary_tissue", "") or "",
                    "analyzer_wound_area_px": int(getattr(report, "wound_area_px", 0) or 0),
                    "analyzer_health_score": round(float(getattr(report, "health_score", 0.0) or 0.0), 4),
                    "analyzer_processing_time_ms": round(
                        float(getattr(report, "processing_time_ms", 0.0) or elapsed_ms),
                        2,
                    ),
                }
            )
        except Exception as exc:
            record.update(
                {
                    "analyzer_success": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

        stage_prediction = stage_classifier.predict(
            image,
            evaluation_context={"wound_area_cm2": 0.0, "pain_score": 0.0},
        )
        stage_payload = stage_prediction.to_dict()
        record.update(
            {
                "predicted_stage": stage_payload["stage_code"],
                "predicted_stage_confidence": stage_payload["confidence"],
                "stage_source": stage_payload["source"],
                "stage_model_available": stage_payload["model_available"],
                "stage_needs_expert_review": stage_payload["needs_expert_review"],
                "stage_considerations": stage_payload["considerations"],
                "stage_visual_signals": stage_payload["visual_signals"],
            }
        )
        records.append(record)

    payload = {
        "dataset": {
            "name": manifest.get("dataset_name"),
            "source_root": manifest.get("source_root"),
            "split": split,
            "samples_per_stage": samples_per_stage,
        },
        "models": {
            "heal_analyzer": "ClinicalWoundAnalyzer headless",
            "pressure_stage_classifier_available": stage_classifier.available,
            "pressure_stage_classifier_version": stage_classifier.model_version,
        },
        "summary": _summarize(records),
        "records": records,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Valida o heal analyzer usando imagens do PIID local.")
    parser.add_argument("--dataset-dir", default="dataset/piid/raw")
    parser.add_argument("--manifest", default="dataset/piid/manifests/piid_lp_split.json")
    parser.add_argument("--output", default="output/validation/piid_heal_analyzer_validation.json")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--samples-per-stage", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = validate(
        dataset_dir=Path(args.dataset_dir),
        manifest_path=Path(args.manifest),
        output_path=Path(args.output),
        split=args.split,
        samples_per_stage=args.samples_per_stage,
        seed=args.seed,
    )
    print(json.dumps({"summary": payload["summary"], "output": args.output}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
