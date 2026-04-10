from __future__ import annotations

import csv
from pathlib import Path

import cv2
import numpy as np

from src.training.segmentation_dataset import (
    build_segmentation_manifest,
    crop_to_mask,
    discover_segmentation_samples,
)


def _write_rgb(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((40, 40, 3), color, dtype=np.uint8)
    cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))


def _write_mask(path: Path, *, radius: int = 10) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mask = np.zeros((40, 40), dtype=np.uint8)
    cv2.circle(mask, (20, 20), radius, 255, thickness=-1)
    cv2.imwrite(str(path), mask)


def test_build_segmentation_manifest_keeps_lesion_groups_in_single_split(tmp_path):
    metadata_path = tmp_path / "metadata.csv"
    rows = []
    for patient_id, lesion_id, color in (
        ("p001", "l001", (220, 120, 120)),
        ("p001", "l002", (220, 220, 120)),
        ("p002", "l003", (120, 220, 120)),
        ("p003", "l004", (120, 120, 220)),
    ):
        for index in range(2):
            stem = f"{patient_id}_{lesion_id}_{index}"
            _write_rgb(tmp_path / "images" / f"{stem}.png", color)
            _write_mask(tmp_path / "masks" / f"{stem}.png")
            rows.append(
                {
                    "image": f"{stem}.png",
                    "patient_id": patient_id,
                    "lesion_id": lesion_id,
                }
            )

    with metadata_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image", "patient_id", "lesion_id"])
        writer.writeheader()
        writer.writerows(rows)

    manifest = build_segmentation_manifest(
        tmp_path,
        metadata_path=metadata_path,
        train_ratio=0.5,
        val_ratio=0.25,
        seed=9,
    )

    lesions_per_split = {
        split_name: {item["lesion_id"] for item in manifest["splits"][split_name]}
        for split_name in ("train", "val", "test")
    }
    assert lesions_per_split["train"].isdisjoint(lesions_per_split["val"])
    assert lesions_per_split["train"].isdisjoint(lesions_per_split["test"])
    assert lesions_per_split["val"].isdisjoint(lesions_per_split["test"])
    assert manifest["summary"]["unique_patients"] == 3
    assert manifest["summary"]["unique_lesions"] == 4


def test_discover_segmentation_samples_infers_patient_and_lesion_from_filename(tmp_path):
    _write_rgb(tmp_path / "images" / "patient-p42_lesion-l7_view1.png", (220, 120, 120))
    _write_mask(tmp_path / "masks" / "patient-p42_lesion-l7_view1.png")

    samples = discover_segmentation_samples(tmp_path)

    assert len(samples) == 1
    assert samples[0].patient_id == "p42"
    assert samples[0].lesion_id == "l7"


def test_crop_to_mask_expands_bbox_with_margin():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[35:65, 40:60] = 255

    cropped_image, cropped_mask, bbox = crop_to_mask(image, mask, margin_ratio=0.2)

    assert cropped_image.shape[:2] == cropped_mask.shape[:2]
    assert bbox[0] < 40
    assert bbox[1] < 35
    assert bbox[2] > 60
    assert bbox[3] > 65
