from __future__ import annotations

import numpy as np


def binary_dice_score(pred_mask: np.ndarray, true_mask: np.ndarray, eps: float = 1.0) -> float:
    pred = pred_mask.astype(bool)
    true = true_mask.astype(bool)
    intersection = np.logical_and(pred, true).sum()
    return float((2.0 * intersection + eps) / (pred.sum() + true.sum() + eps))


def binary_iou_score(pred_mask: np.ndarray, true_mask: np.ndarray, eps: float = 1.0) -> float:
    pred = pred_mask.astype(bool)
    true = true_mask.astype(bool)
    intersection = np.logical_and(pred, true).sum()
    union = np.logical_or(pred, true).sum()
    return float((intersection + eps) / (union + eps))


def binary_average_precision(labels: np.ndarray, scores: np.ndarray) -> float:
    labels = labels.astype(np.uint8).reshape(-1)
    scores = scores.astype(np.float32).reshape(-1)
    if labels.size == 0:
        return 0.0
    positive_count = int(labels.sum())
    if positive_count == 0:
        return 0.0

    order = np.argsort(-scores)
    labels_sorted = labels[order]
    tp = np.cumsum(labels_sorted == 1)
    fp = np.cumsum(labels_sorted == 0)
    precision = tp / np.maximum(tp + fp, 1)
    recall = tp / positive_count

    precision = np.concatenate(([1.0], precision))
    recall = np.concatenate(([0.0], recall))
    ap = np.sum((recall[1:] - recall[:-1]) * precision[1:])
    return float(ap)


def binary_ece(
    labels: np.ndarray,
    scores: np.ndarray,
    *,
    threshold: float = 0.5,
    n_bins: int = 15,
    max_samples: int = 200_000,
) -> float:
    labels = labels.astype(np.uint8).reshape(-1)
    scores = scores.astype(np.float32).reshape(-1)
    if labels.size == 0:
        return 0.0

    if labels.size > max_samples:
        rng = np.random.default_rng(42)
        indices = rng.choice(labels.size, size=max_samples, replace=False)
        labels = labels[indices]
        scores = scores[indices]

    predictions = (scores >= threshold).astype(np.uint8)
    confidence = np.where(predictions == 1, scores, 1.0 - scores)
    correctness = (predictions == labels).astype(np.float32)

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for idx in range(n_bins):
        if idx == 0:
            mask = (confidence >= bin_edges[idx]) & (confidence <= bin_edges[idx + 1])
        else:
            mask = (confidence > bin_edges[idx]) & (confidence <= bin_edges[idx + 1])
        if not np.any(mask):
            continue
        avg_conf = float(confidence[mask].mean())
        avg_acc = float(correctness[mask].mean())
        weight = float(mask.mean())
        ece += weight * abs(avg_acc - avg_conf)
    return float(ece)


def multiclass_confusion_matrix(
    predictions: np.ndarray,
    targets: np.ndarray,
    *,
    num_classes: int,
) -> np.ndarray:
    confusion = np.zeros((num_classes, num_classes), dtype=np.int64)
    preds = predictions.reshape(-1).astype(np.int64)
    truth = targets.reshape(-1).astype(np.int64)
    valid = (truth >= 0) & (truth < num_classes)
    preds = preds[valid]
    truth = truth[valid]
    for target_class, predicted_class in zip(truth, preds):
        confusion[target_class, predicted_class] += 1
    return confusion


def per_class_recall(confusion: np.ndarray) -> list[float]:
    recalls: list[float] = []
    for class_index in range(confusion.shape[0]):
        tp = confusion[class_index, class_index]
        fn = confusion[class_index].sum() - tp
        recalls.append(float(tp / max(tp + fn, 1)))
    return recalls


def per_class_iou(confusion: np.ndarray) -> list[float]:
    scores: list[float] = []
    for class_index in range(confusion.shape[0]):
        tp = confusion[class_index, class_index]
        fn = confusion[class_index].sum() - tp
        fp = confusion[:, class_index].sum() - tp
        scores.append(float(tp / max(tp + fn + fp, 1)))
    return scores


def per_class_dice(confusion: np.ndarray) -> list[float]:
    scores: list[float] = []
    for class_index in range(confusion.shape[0]):
        tp = confusion[class_index, class_index]
        fn = confusion[class_index].sum() - tp
        fp = confusion[:, class_index].sum() - tp
        scores.append(float((2.0 * tp) / max((2.0 * tp) + fn + fp, 1)))
    return scores
