from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.diagnosis.pressure_injury_stage_classifier import (
    PRESSURE_STAGE_CODES,
    PressureInjuryStageClassifier,
)


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _base_probabilities(
    classifier: PressureInjuryStageClassifier,
    image_bgr: np.ndarray,
) -> tuple[dict[str, float], Any]:
    signals = classifier._extract_visual_signals(image_bgr)
    heuristic = classifier._heuristic_probabilities(signals)
    model = classifier._predict_model_probabilities(image_bgr)
    if model:
        probabilities = {
            stage_code: model[stage_code] * 0.8 + heuristic[stage_code] * 0.2
            for stage_code in PRESSURE_STAGE_CODES
        }
    else:
        probabilities = heuristic
    total = sum(probabilities.values()) or 1.0
    probabilities = {stage: float(value / total) for stage, value in probabilities.items()}
    return probabilities, signals


def _collect_records(
    manifest: dict[str, Any],
    split_names: list[str],
    classifier: PressureInjuryStageClassifier,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for split_name in split_names:
        for sample in manifest["splits"].get(split_name, []):
            image = cv2.imread(sample["path"])
            if image is None:
                continue
            probabilities, signals = _base_probabilities(classifier, image)
            features = classifier.stage34_feature_vector(probabilities, signals)
            records.append(
                {
                    "split": split_name,
                    "path": sample["path"],
                    "true_stage": sample["stage_code"],
                    "probabilities": probabilities,
                    "features": features,
                }
            )
    return records


def _standardize(features: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = features.mean(axis=0)
    scale = features.std(axis=0)
    scale = np.where(scale < 1e-6, 1.0, scale)
    return (features - mean) / scale, mean, scale


def _fit_logistic(
    features: np.ndarray,
    targets: np.ndarray,
    *,
    steps: int = 2500,
    learning_rate: float = 0.05,
    l2: float = 0.01,
) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    normalized, mean, scale = _standardize(features)
    weights = np.zeros(normalized.shape[1], dtype=np.float64)
    pos_rate = float(np.clip(targets.mean(), 1e-3, 1 - 1e-3))
    bias = float(np.log(pos_rate / (1.0 - pos_rate)))

    for _ in range(steps):
        logits = normalized @ weights + bias
        probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -40.0, 40.0)))
        error = probs - targets
        grad_w = (normalized.T @ error) / len(targets) + l2 * weights
        grad_b = float(error.mean())
        weights -= learning_rate * grad_w
        bias -= learning_rate * grad_b

    return weights, bias, mean, scale


def _pair_probability(features: np.ndarray, weights: np.ndarray, bias: float, mean: np.ndarray, scale: np.ndarray) -> np.ndarray:
    normalized = (features - mean) / scale
    logits = normalized @ weights + bias
    return 1.0 / (1.0 + np.exp(-np.clip(logits, -40.0, 40.0)))


def _apply_pair_calibration(
    probabilities: dict[str, float],
    pair_probability_stage4: float,
    *,
    min_pair_mass: float,
) -> dict[str, float]:
    pair_mass = float(probabilities.get("stage_3", 0.0) + probabilities.get("stage_4", 0.0))
    if pair_mass < min_pair_mass:
        return dict(probabilities)
    calibrated = dict(probabilities)
    calibrated["stage_4"] = pair_mass * float(pair_probability_stage4)
    calibrated["stage_3"] = pair_mass * (1.0 - float(pair_probability_stage4))
    total = sum(calibrated.values()) or 1.0
    return {stage: float(value / total) for stage, value in calibrated.items()}


def _evaluate_records(
    records: list[dict[str, Any]],
    *,
    weights: np.ndarray | None = None,
    bias: float = 0.0,
    mean: np.ndarray | None = None,
    scale: np.ndarray | None = None,
    min_pair_mass: float = 0.20,
) -> dict[str, Any]:
    confusion = {true: {pred: 0 for pred in PRESSURE_STAGE_CODES} for true in PRESSURE_STAGE_CODES}
    correct = 0
    for record in records:
        probabilities = dict(record["probabilities"])
        if weights is not None and mean is not None and scale is not None:
            feature_array = np.array([record["features"]], dtype=np.float64)
            pair_prob = float(_pair_probability(feature_array, weights, bias, mean, scale)[0])
            probabilities = _apply_pair_calibration(probabilities, pair_prob, min_pair_mass=min_pair_mass)
        predicted = max(probabilities, key=probabilities.get)
        true_stage = record["true_stage"]
        confusion[true_stage][predicted] += 1
        correct += int(predicted == true_stage)

    per_stage = {}
    for stage in PRESSURE_STAGE_CODES:
        total = sum(confusion[stage].values())
        per_stage[stage] = round(confusion[stage][stage] / total, 4) if total else 0.0
    return {
        "accuracy": round(correct / max(1, len(records)), 4),
        "per_stage_accuracy": per_stage,
        "confusion": confusion,
    }


def _logit(probability: float) -> float:
    probability = float(np.clip(probability, 1e-4, 1 - 1e-4))
    return float(np.log(probability / (1.0 - probability)))


def calibrate(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = Path(args.manifest)
    metadata_path = Path(args.metadata)
    manifest = _load_manifest(manifest_path)
    classifier = PressureInjuryStageClassifier(
        weights_path=args.weights,
        metadata_path=args.metadata,
        enable_pairwise_calibration=False,
    )
    if not classifier.available:
        raise RuntimeError("Classificador LP nao esta disponivel; treine ou informe pesos validos antes de calibrar.")

    train_records = _collect_records(manifest, ["train"], classifier)
    val_records = _collect_records(manifest, ["val"], classifier)
    test_records = _collect_records(manifest, ["test"], classifier)

    train_pair = [record for record in train_records if record["true_stage"] in {"stage_3", "stage_4"}]
    if len(train_pair) < 20:
        raise RuntimeError("Amostras stage_3/stage_4 insuficientes para calibracao.")

    x_train = np.array([record["features"] for record in train_pair], dtype=np.float64)
    y_train = np.array([1.0 if record["true_stage"] == "stage_4" else 0.0 for record in train_pair], dtype=np.float64)
    weights, raw_bias, mean, scale = _fit_logistic(
        x_train,
        y_train,
        steps=args.steps,
        learning_rate=args.learning_rate,
        l2=args.l2,
    )

    val_pair = [record for record in val_records if record["true_stage"] in {"stage_3", "stage_4"}]
    x_val = np.array([record["features"] for record in val_pair], dtype=np.float64)
    y_val = np.array([1.0 if record["true_stage"] == "stage_4" else 0.0 for record in val_pair], dtype=np.float64)
    val_pair_probs = _pair_probability(x_val, weights, raw_bias, mean, scale) if len(val_pair) else np.array([])

    best_threshold = 0.5
    best_balanced = -1.0
    for threshold in np.linspace(0.30, 0.70, 41):
        if not len(val_pair_probs):
            break
        predicted = (val_pair_probs >= threshold).astype(float)
        stage3_mask = y_val == 0.0
        stage4_mask = y_val == 1.0
        stage3_acc = float((predicted[stage3_mask] == 0.0).mean()) if stage3_mask.any() else 0.0
        stage4_acc = float((predicted[stage4_mask] == 1.0).mean()) if stage4_mask.any() else 0.0
        balanced = (stage3_acc + stage4_acc) / 2.0
        if balanced > best_balanced:
            best_balanced = balanced
            best_threshold = float(threshold)

    adjusted_bias = raw_bias - _logit(best_threshold)
    before = {
        "train": _evaluate_records(train_records),
        "val": _evaluate_records(val_records),
        "test": _evaluate_records(test_records),
    }
    after = {
        "train": _evaluate_records(train_records, weights=weights, bias=adjusted_bias, mean=mean, scale=scale, min_pair_mass=args.min_pair_mass),
        "val": _evaluate_records(val_records, weights=weights, bias=adjusted_bias, mean=mean, scale=scale, min_pair_mass=args.min_pair_mass),
        "test": _evaluate_records(test_records, weights=weights, bias=adjusted_bias, mean=mean, scale=scale, min_pair_mass=args.min_pair_mass),
    }
    enabled = (
        after["val"]["accuracy"] > before["val"]["accuracy"]
        and after["val"]["per_stage_accuracy"]["stage_3"] >= before["val"]["per_stage_accuracy"]["stage_3"]
        and after["val"]["per_stage_accuracy"]["stage_4"] >= before["val"]["per_stage_accuracy"]["stage_4"]
    )

    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    metadata["stage34_calibration"] = {
        "enabled": enabled,
        "type": "logistic_pairwise_v1",
        "positive_class": "stage_4",
        "negative_class": "stage_3",
        "feature_names": classifier.stage34_feature_names(),
        "weights": [round(float(value), 8) for value in weights],
        "bias": round(float(adjusted_bias), 8),
        "raw_bias": round(float(raw_bias), 8),
        "decision_threshold": round(float(best_threshold), 4),
        "min_pair_mass": round(float(args.min_pair_mass), 4),
        "feature_mean": [round(float(value), 8) for value in mean],
        "feature_scale": [round(float(value), 8) for value in scale],
        "train_pair_count": len(train_pair),
        "validation_pair_count": len(val_pair),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "metrics_before": before,
        "metrics_after": after,
        "notes": [
            "Calibracao local para reduzir confusao stage_3 vs stage_4 no PIID.",
            "Nao altera pesos da ResNet; ajusta apenas distribuicao stage_3/stage_4 em inferencia.",
            "Ativada somente quando melhora a acuracia geral de validacao sem piorar stage_3/stage_4.",
        ],
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"metadata_path": str(metadata_path), "before": before, "after": after}


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibra o classificador LP para reduzir confusao stage_3/stage_4.")
    parser.add_argument("--manifest", default="dataset/piid/manifests/piid_lp_split.json")
    parser.add_argument("--weights", default="models/pressure_injury_stage_classifier/pressure_injury_stage_resnet50.pth")
    parser.add_argument("--metadata", default="models/pressure_injury_stage_classifier/model_metadata.json")
    parser.add_argument("--steps", type=int, default=2500)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--l2", type=float, default=0.01)
    parser.add_argument("--min-pair-mass", type=float, default=0.20)
    args = parser.parse_args()
    result = calibrate(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
