from pathlib import Path

from PIL import Image

from src.training.pressure_injury_dataset import (
    PRESSURE_INJURY_STAGE_ORDER,
    build_pressure_injury_manifest,
    canonical_pressure_injury_stage,
)


def _write_png(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), color=color).save(path)


def test_canonical_pressure_injury_stage_supports_aliases():
    assert canonical_pressure_injury_stage("stage_1") == "stage_1"
    assert canonical_pressure_injury_stage("Stage-2") == "stage_2"
    assert canonical_pressure_injury_stage("III") == "stage_3"
    assert canonical_pressure_injury_stage("4") == "stage_4"


def test_build_pressure_injury_manifest_creates_stratified_splits(tmp_path):
    colors = {
        "stage_1": (255, 190, 210),
        "stage_2": (210, 70, 70),
        "stage_3": (220, 210, 90),
        "stage_4": (25, 25, 25),
    }
    for stage_code in PRESSURE_INJURY_STAGE_ORDER:
        for index in range(4):
            _write_png(tmp_path / stage_code / f"{stage_code}_{index}.png", colors[stage_code])

    manifest = build_pressure_injury_manifest(tmp_path, train_ratio=0.5, val_ratio=0.25, seed=7)

    assert manifest["class_names"] == PRESSURE_INJURY_STAGE_ORDER
    assert manifest["summary"]["total_samples"] == 16
    assert manifest["summary"]["split_sizes"] == {"train": 8, "val": 4, "test": 4}
    for split_name in ("train", "val", "test"):
        split = manifest["splits"][split_name]
        assert split
        assert {item["stage_code"] for item in split} == set(PRESSURE_INJURY_STAGE_ORDER)
