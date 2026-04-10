from __future__ import annotations

import numpy as np

from src.training.segmentation_metrics import (
    binary_average_precision,
    binary_dice_score,
    binary_ece,
    binary_iou_score,
    multiclass_confusion_matrix,
    per_class_dice,
    per_class_iou,
    per_class_recall,
)


def test_binary_metrics_capture_good_overlap_and_calibration():
    true_mask = np.array([[1, 1], [0, 0]], dtype=np.uint8)
    pred_mask = np.array([[1, 1], [1, 0]], dtype=np.uint8)
    scores = np.array([[0.95, 0.88], [0.55, 0.05]], dtype=np.float32)

    assert binary_dice_score(pred_mask, true_mask) > 0.79
    assert binary_iou_score(pred_mask, true_mask) > 0.66
    assert binary_average_precision(true_mask, scores) > 0.99
    assert binary_ece(true_mask, scores, threshold=0.5) < 0.2


def test_multiclass_confusion_helpers_return_per_class_scores():
    predictions = np.array([[0, 1, 2], [2, 2, 1]], dtype=np.uint8)
    targets = np.array([[0, 1, 1], [2, 2, 1]], dtype=np.uint8)

    confusion = multiclass_confusion_matrix(predictions, targets, num_classes=3)

    recalls = per_class_recall(confusion)
    ious = per_class_iou(confusion)
    dice_scores = per_class_dice(confusion)

    assert confusion.shape == (3, 3)
    assert recalls[1] < 1.0
    assert ious[2] > 0.6
    assert dice_scores[0] == 1.0
