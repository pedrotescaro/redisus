from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PRESSURE_INJURY_STAGE_ORDER = ["stage_1", "stage_2", "stage_3", "stage_4"]
PRESSURE_INJURY_STAGE_LABELS = {
    "stage_1": "Lesao por Pressao - Estagio 1",
    "stage_2": "Lesao por Pressao - Estagio 2",
    "stage_3": "Lesao por Pressao - Estagio 3",
    "stage_4": "Lesao por Pressao - Estagio 4",
}
_STAGE_ALIASES = {
    "1": "stage_1",
    "stage1": "stage_1",
    "stage_1": "stage_1",
    "stage-1": "stage_1",
    "stg1": "stage_1",
    "i": "stage_1",
    "2": "stage_2",
    "stage2": "stage_2",
    "stage_2": "stage_2",
    "stage-2": "stage_2",
    "stg2": "stage_2",
    "ii": "stage_2",
    "3": "stage_3",
    "stage3": "stage_3",
    "stage_3": "stage_3",
    "stage-3": "stage_3",
    "stg3": "stage_3",
    "iii": "stage_3",
    "4": "stage_4",
    "stage4": "stage_4",
    "stage_4": "stage_4",
    "stage-4": "stage_4",
    "stg4": "stage_4",
    "iv": "stage_4",
}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


@dataclass(frozen=True, slots=True)
class PressureInjurySample:
    path: str
    stage_code: str
    stage_index: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "stage_code": self.stage_code,
            "stage_index": self.stage_index,
            "stage_label": PRESSURE_INJURY_STAGE_LABELS[self.stage_code],
        }


def canonical_pressure_injury_stage(value: Any) -> str | None:
    token = str(value or "").strip().lower().replace(" ", "_")
    token = token.replace("__", "_")
    return _STAGE_ALIASES.get(token)


def _iter_image_files(folder: Path):
    for file_path in sorted(folder.iterdir()):
        if file_path.is_file() and file_path.suffix.lower() in _IMAGE_EXTENSIONS:
            yield file_path


def discover_pressure_injury_samples(dataset_root: str | Path) -> list[PressureInjurySample]:
    root = Path(dataset_root)
    if not root.exists():
        raise FileNotFoundError(f"Diretorio do dataset PIID nao encontrado: {root}")

    samples: list[PressureInjurySample] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        stage_code = canonical_pressure_injury_stage(child.name)
        if not stage_code:
            continue
        stage_index = PRESSURE_INJURY_STAGE_ORDER.index(stage_code)
        for image_path in _iter_image_files(child):
            samples.append(
                PressureInjurySample(
                    path=str(image_path.resolve()),
                    stage_code=stage_code,
                    stage_index=stage_index,
                )
            )

    if not samples:
        raise ValueError(
            "Nenhuma imagem de lesao por pressao encontrada. "
            "Esperado: pastas stage_1, stage_2, stage_3 e stage_4 em dataset/piid/raw."
        )
    return samples


def summarize_pressure_injury_samples(samples: list[PressureInjurySample]) -> dict[str, Any]:
    per_stage = {stage_code: 0 for stage_code in PRESSURE_INJURY_STAGE_ORDER}
    for sample in samples:
        per_stage[sample.stage_code] = per_stage.get(sample.stage_code, 0) + 1
    return {
        "total_samples": len(samples),
        "per_stage": {
            stage_code: {
                "count": per_stage.get(stage_code, 0),
                "label": PRESSURE_INJURY_STAGE_LABELS[stage_code],
            }
            for stage_code in PRESSURE_INJURY_STAGE_ORDER
        },
    }


def _split_counts(total: int, *, train_ratio: float, val_ratio: float) -> tuple[int, int, int]:
    train_count = int(round(total * train_ratio))
    val_count = int(round(total * val_ratio))
    if train_count <= 0:
        train_count = 1
    if total >= 3 and val_count <= 0:
        val_count = 1
    if train_count + val_count >= total:
        if val_count > 1:
            val_count -= 1
        elif train_count > 1:
            train_count -= 1
    test_count = max(0, total - train_count - val_count)
    if total >= 3 and test_count <= 0:
        if train_count > val_count and train_count > 1:
            train_count -= 1
        elif val_count > 1:
            val_count -= 1
        test_count = total - train_count - val_count
    return train_count, val_count, test_count


def stratified_pressure_injury_split(
    samples: list[PressureInjurySample],
    *,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    seed: int = 42,
) -> tuple[list[PressureInjurySample], list[PressureInjurySample], list[PressureInjurySample]]:
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio deve estar entre 0 e 1.")
    if not 0 <= val_ratio < 1:
        raise ValueError("val_ratio deve estar entre 0 e 1.")
    if train_ratio + val_ratio >= 1:
        raise ValueError("train_ratio + val_ratio deve ser menor que 1.")

    rng = random.Random(seed)
    grouped: dict[str, list[PressureInjurySample]] = {stage_code: [] for stage_code in PRESSURE_INJURY_STAGE_ORDER}
    for sample in samples:
        grouped.setdefault(sample.stage_code, []).append(sample)

    train: list[PressureInjurySample] = []
    val: list[PressureInjurySample] = []
    test: list[PressureInjurySample] = []

    for stage_code in PRESSURE_INJURY_STAGE_ORDER:
        stage_samples = list(grouped.get(stage_code) or [])
        rng.shuffle(stage_samples)
        train_count, val_count, _ = _split_counts(
            len(stage_samples),
            train_ratio=train_ratio,
            val_ratio=val_ratio,
        )
        train.extend(stage_samples[:train_count])
        val.extend(stage_samples[train_count:train_count + val_count])
        test.extend(stage_samples[train_count + val_count:])

    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)
    return train, val, test


def build_pressure_injury_manifest(
    dataset_root: str | Path,
    *,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    seed: int = 42,
) -> dict[str, Any]:
    samples = discover_pressure_injury_samples(dataset_root)
    train, val, test = stratified_pressure_injury_split(
        samples,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        seed=seed,
    )
    manifest = {
        "dataset_name": "PIID Pressure Injury Staging",
        "source_root": str(Path(dataset_root).resolve()),
        "seed": seed,
        "class_names": list(PRESSURE_INJURY_STAGE_ORDER),
        "class_labels": dict(PRESSURE_INJURY_STAGE_LABELS),
        "summary": summarize_pressure_injury_samples(samples),
        "splits": {
            "train": [sample.to_dict() for sample in train],
            "val": [sample.to_dict() for sample in val],
            "test": [sample.to_dict() for sample in test],
        },
    }
    manifest["summary"]["split_sizes"] = {
        "train": len(train),
        "val": len(val),
        "test": len(test),
    }
    return manifest


def write_pressure_injury_manifest(manifest: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
