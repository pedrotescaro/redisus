from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import torch
from PIL import Image

from ml.scripts.audit_classification_dataset import audit
from ml.scripts.prepare_co2wounds_v2 import (
    base_record,
    merge_exact_duplicate_annotations,
)
from src.processing.wound_segmentation_dl import (
    MODEL_ARCHITECTURE,
    SmallUNet,
    WoundSegmentationPredictor,
    clean_binary_mask,
    letterbox_pil,
    undo_letterbox,
)


def test_letterbox_preserves_geometry_and_restores_shape():
    image = Image.new("L", (80, 40), 255)
    prepared, metadata = letterbox_pil(
        image,
        64,
        resample=Image.Resampling.NEAREST,
        fill=0,
    )
    array = np.asarray(prepared)

    assert prepared.size == (64, 64)
    assert metadata.resized_width == 64
    assert metadata.resized_height == 32
    restored = undo_letterbox(array, metadata, interpolation=cv2.INTER_NEAREST)
    assert restored.shape == (40, 80)
    assert np.all(restored == 255)


def test_clean_binary_mask_removes_speckle_and_keeps_real_components():
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[10:30, 10:30] = 255
    mask[60:85, 65:90] = 255
    mask[50, 50] = 255

    cleaned = clean_binary_mask(mask, min_component_ratio=0.001)

    assert cleaned[50, 50] == 0
    assert cleaned[20, 20] == 255
    assert cleaned[70, 75] == 255


def test_predictor_requires_explicit_non_commercial_acceptance(tmp_path: Path):
    model = SmallUNet(base_channels=8)
    checkpoint = tmp_path / "model.pt"
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "architecture": MODEL_ARCHITECTURE,
            "base_channels": 8,
            "license_scope": "academic_research_non_commercial_only",
            "training_args": {"image_size": 32},
        },
        checkpoint,
    )

    with pytest.raises(PermissionError):
        WoundSegmentationPredictor(checkpoint)


def test_predictor_abstains_from_full_frame_untrained_mask(tmp_path: Path):
    model = SmallUNet(base_channels=8)
    for parameter in model.parameters():
        torch.nn.init.zeros_(parameter)
    checkpoint = tmp_path / "model.pt"
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "architecture": MODEL_ARCHITECTURE,
            "base_channels": 8,
            "license_scope": "academic_research_non_commercial_only",
            "training_args": {"image_size": 32},
            "decision_threshold": 0.5,
            "epoch": 1,
        },
        checkpoint,
    )
    predictor = WoundSegmentationPredictor(checkpoint, allow_non_commercial_research=True)

    prediction = predictor.predict(np.zeros((24, 48, 3), dtype=np.uint8))

    assert prediction.accepted is False
    assert prediction.reason == "predicted_wound_too_large"
    assert prediction.mask.shape == (24, 48)
    assert "mask" not in prediction.metadata()


def test_duplicate_images_merge_masks_and_stay_in_one_split(tmp_path: Path):
    image_path_a = tmp_path / "train_a.png"
    image_path_b = tmp_path / "val_b.png"
    mask_path_a = tmp_path / "mask_a.png"
    mask_path_b = tmp_path / "mask_b.png"
    pixels = np.full((16, 16, 3), 120, dtype=np.uint8)
    Image.fromarray(pixels).save(image_path_a)
    Image.fromarray(pixels).save(image_path_b)
    mask_a = np.zeros((16, 16), dtype=np.uint8)
    mask_b = np.zeros((16, 16), dtype=np.uint8)
    mask_a[2:6, 2:6] = 255
    mask_b[10:14, 10:14] = 255
    Image.fromarray(mask_a).save(mask_path_a)
    Image.fromarray(mask_b).save(mask_path_b)
    train = [base_record("a", image_path_a, mask_path_a, "train")]
    val = [base_record("b", image_path_b, mask_path_b, "val")]

    merged_train, merged_val, report = merge_exact_duplicate_annotations(
        train,
        val,
        output_dir=tmp_path / "merged",
    )

    assert merged_train == []
    assert len(merged_val) == 1
    assert report["cross_split_duplicate_groups"] == 1
    merged_mask = np.asarray(Image.open(merged_val[0]["mask"]).convert("L"))
    assert merged_mask[3, 3] == 255
    assert merged_mask[11, 11] == 255


def test_classification_audit_blocks_identical_cross_label_images(tmp_path: Path):
    for label in ("pressure", "venous"):
        (tmp_path / label).mkdir()
    pixels = np.full((12, 12, 3), 80, dtype=np.uint8)
    Image.fromarray(pixels).save(tmp_path / "pressure" / "one.png")
    Image.fromarray(pixels).save(tmp_path / "venous" / "two.png")

    report = audit(tmp_path, near_duplicate_distance=0)

    assert report["files"] == 2
    assert report["unique_exact_hashes"] == 1
    assert report["cross_label_exact_conflict_groups"] == 1
    assert "exact_images_with_conflicting_labels" in report["release_blockers"]
