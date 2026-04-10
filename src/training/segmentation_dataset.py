from __future__ import annotations

import csv
import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
MASK_DIR_NAMES = ("masks", "labels")
IMAGE_DIR_NAMES = ("images",)

PATIENT_FIELD_ALIASES = (
    "patient_id",
    "patient",
    "subject_id",
    "subject",
    "person_id",
)
LESION_FIELD_ALIASES = (
    "lesion_id",
    "wound_id",
    "case_id",
    "ulcer_id",
    "lesion",
    "wound",
    "case",
)
IMAGE_FIELD_ALIASES = (
    "image",
    "image_path",
    "filename",
    "file_name",
    "name",
    "path",
)
MASK_FIELD_ALIASES = (
    "mask",
    "mask_path",
    "label_path",
)

PATIENT_PATTERNS = (
    re.compile(r"(?:^|[_-])(patient|pat|subject|person)[_-]?([a-z0-9]+)", re.IGNORECASE),
    re.compile(r"(?:^|[_-])p([0-9]{2,})", re.IGNORECASE),
)
LESION_PATTERNS = (
    re.compile(r"(?:^|[_-])(lesion|wound|ulcer|case)[_-]?([a-z0-9]+)", re.IGNORECASE),
    re.compile(r"(?:^|[_-])l([0-9]{2,})", re.IGNORECASE),
)


@dataclass(frozen=True, slots=True)
class SegmentationSample:
    image_path: str
    mask_path: str
    patient_id: str | None = None
    lesion_id: str | None = None
    split_group: str | None = None
    source_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "image_path": self.image_path,
            "mask_path": self.mask_path,
        }
        if self.patient_id:
            payload["patient_id"] = self.patient_id
        if self.lesion_id:
            payload["lesion_id"] = self.lesion_id
        if self.split_group:
            payload["split_group"] = self.split_group
        if self.source_name:
            payload["source_name"] = self.source_name
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


def _normalize_token(value: Any) -> str | None:
    token = str(value or "").strip()
    if not token:
        return None
    token = re.sub(r"\s+", "_", token)
    return token


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace("\\", "/")


def _stem_key(value: str) -> str:
    normalized = _normalize_key(value)
    return Path(normalized).stem


def _first_present(record: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for alias in aliases:
        if alias in record and record[alias] not in (None, ""):
            return record[alias]
    return None


def _infer_with_patterns(path: Path, patterns: tuple[re.Pattern[str], ...]) -> str | None:
    candidates = [path.stem, *path.parts[-4:]]
    for candidate in candidates:
        for pattern in patterns:
            match = pattern.search(candidate)
            if not match:
                continue
            if match.lastindex and match.lastindex >= 2:
                return _normalize_token(match.group(2))
            if match.lastindex:
                return _normalize_token(match.group(1))
    return None


def infer_patient_id(path: str | Path) -> str | None:
    return _infer_with_patterns(Path(path), PATIENT_PATTERNS)


def infer_lesion_id(path: str | Path) -> str | None:
    return _infer_with_patterns(Path(path), LESION_PATTERNS)


def load_metadata_lookup(metadata_path: str | Path | None) -> dict[str, dict[str, Any]]:
    if metadata_path is None:
        return {}

    path = Path(metadata_path)
    if not path.exists():
        return {}

    suffix = path.suffix.lower()
    records: list[dict[str, Any]] = []

    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            records.extend(dict(row) for row in reader)
    elif suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    elif suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            records.extend(item for item in payload if isinstance(item, dict))
        elif isinstance(payload, dict):
            if isinstance(payload.get("samples"), list):
                records.extend(item for item in payload["samples"] if isinstance(item, dict))
            elif isinstance(payload.get("records"), list):
                records.extend(item for item in payload["records"] if isinstance(item, dict))
            elif IMAGE_FIELD_ALIASES[0] in payload or any(alias in payload for alias in IMAGE_FIELD_ALIASES):
                records.append(payload)
    else:
        return {}

    lookup: dict[str, dict[str, Any]] = {}
    for record in records:
        raw_image = _first_present(record, IMAGE_FIELD_ALIASES)
        raw_mask = _first_present(record, MASK_FIELD_ALIASES)
        keys = set()
        if raw_image:
            keys.add(_normalize_key(str(raw_image)))
            keys.add(_stem_key(str(raw_image)))
        if raw_mask:
            keys.add(_normalize_key(str(raw_mask)))
            keys.add(_stem_key(str(raw_mask)))
        if "id" in record:
            keys.add(_normalize_key(str(record["id"])))
        for key in keys:
            lookup[key] = dict(record)
    return lookup


def _candidate_pair_roots(root: Path, split: str | None) -> list[tuple[Path, Path, str | None]]:
    candidates: list[tuple[Path, Path, str | None]] = []

    def append_if_exists(base: Path, source_name: str | None = None) -> None:
        for image_dir_name in IMAGE_DIR_NAMES:
            image_dir = base / image_dir_name
            if not image_dir.exists():
                continue
            for mask_dir_name in MASK_DIR_NAMES:
                mask_dir = base / mask_dir_name
                if mask_dir.exists():
                    candidates.append((image_dir, mask_dir, source_name))

    if split:
        append_if_exists(root / split, split)
        append_if_exists(root / "splits" / split, split)
    else:
        append_if_exists(root)
        for split_name in ("train", "val", "test"):
            append_if_exists(root / split_name, split_name)
            append_if_exists(root / "splits" / split_name, split_name)

    deduped: list[tuple[Path, Path, str | None]] = []
    seen = set()
    for image_dir, mask_dir, source_name in candidates:
        key = (str(image_dir.resolve()), str(mask_dir.resolve()))
        if key in seen:
            continue
        seen.add(key)
        deduped.append((image_dir, mask_dir, source_name))
    return deduped


def discover_segmentation_samples(
    dataset_root: str | Path,
    *,
    metadata_path: str | Path | None = None,
    split: str | None = None,
) -> list[SegmentationSample]:
    root = Path(dataset_root)
    if not root.exists():
        raise FileNotFoundError(f"Diretorio do dataset nao encontrado: {root}")

    metadata = load_metadata_lookup(metadata_path)
    samples: list[SegmentationSample] = []

    for image_dir, mask_dir, source_name in _candidate_pair_roots(root, split):
        masks_by_stem = {
            mask_path.stem: mask_path
            for mask_path in sorted(mask_dir.iterdir())
            if mask_path.is_file() and mask_path.suffix.lower() in IMAGE_EXTENSIONS
        }
        for image_path in sorted(image_dir.iterdir()):
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            mask_path = masks_by_stem.get(image_path.stem)
            if mask_path is None:
                continue

            metadata_record = (
                metadata.get(_normalize_key(str(image_path)))
                or metadata.get(_stem_key(str(image_path)))
                or metadata.get(_normalize_key(image_path.name))
                or {}
            )
            patient_id = _normalize_token(_first_present(metadata_record, PATIENT_FIELD_ALIASES))
            lesion_id = _normalize_token(_first_present(metadata_record, LESION_FIELD_ALIASES))
            split_group = _normalize_token(metadata_record.get("split_group"))

            if not patient_id:
                patient_id = infer_patient_id(image_path)
            if not lesion_id:
                lesion_id = infer_lesion_id(image_path)

            samples.append(
                SegmentationSample(
                    image_path=str(image_path.resolve()),
                    mask_path=str(mask_path.resolve()),
                    patient_id=patient_id,
                    lesion_id=lesion_id,
                    split_group=split_group,
                    source_name=source_name,
                    metadata=metadata_record,
                )
            )

    if not samples:
        raise ValueError(
            "Nenhum par imagem/mascara encontrado. Esperado: images/ + masks/ ou train/images + train/labels."
        )
    return samples


def _group_key(sample: SegmentationSample) -> str:
    return (
        sample.split_group
        or sample.lesion_id
        or sample.patient_id
        or Path(sample.image_path).stem
    )


def summarize_segmentation_samples(samples: list[SegmentationSample]) -> dict[str, Any]:
    unique_patients = {sample.patient_id for sample in samples if sample.patient_id}
    unique_lesions = {sample.lesion_id for sample in samples if sample.lesion_id}
    groups = {_group_key(sample) for sample in samples}
    return {
        "total_samples": len(samples),
        "unique_patients": len(unique_patients),
        "unique_lesions": len(unique_lesions),
        "unique_groups": len(groups),
    }


def grouped_train_val_test_split(
    samples: list[SegmentationSample],
    *,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    seed: int = 42,
) -> tuple[list[SegmentationSample], list[SegmentationSample], list[SegmentationSample]]:
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio deve estar entre 0 e 1.")
    if not 0 <= val_ratio < 1:
        raise ValueError("val_ratio deve estar entre 0 e 1.")
    if train_ratio + val_ratio >= 1:
        raise ValueError("train_ratio + val_ratio deve ser menor que 1.")

    rng = random.Random(seed)
    grouped: dict[str, list[SegmentationSample]] = {}
    for sample in samples:
        grouped.setdefault(_group_key(sample), []).append(sample)

    group_items = list(grouped.items())
    rng.shuffle(group_items)
    group_items.sort(key=lambda item: len(item[1]), reverse=True)

    total_samples = len(samples)
    target_counts = {
        "train": int(round(total_samples * train_ratio)),
        "val": int(round(total_samples * val_ratio)),
    }
    target_counts["test"] = max(0, total_samples - target_counts["train"] - target_counts["val"])
    if total_samples >= 3 and target_counts["test"] == 0:
        target_counts["test"] = 1
        if target_counts["train"] >= target_counts["val"] and target_counts["train"] > 1:
            target_counts["train"] -= 1
        elif target_counts["val"] > 1:
            target_counts["val"] -= 1

    assigned_counts = {"train": 0, "val": 0, "test": 0}
    split_items = {"train": [], "val": [], "test": []}

    def best_split(group_size: int) -> str:
        remaining = {
            split_name: target_counts[split_name] - assigned_counts[split_name]
            for split_name in ("train", "val", "test")
        }
        viable = [
            split_name
            for split_name, remainder in remaining.items()
            if remainder >= group_size
        ]
        if viable:
            viable.sort(key=lambda name: (remaining[name], target_counts[name]), reverse=True)
            return viable[0]

        ranked = sorted(
            ("train", "val", "test"),
            key=lambda name: (
                remaining[name],
                -assigned_counts[name],
                target_counts[name],
            ),
            reverse=True,
        )
        return ranked[0]

    for _, group_samples in group_items:
        chosen_split = best_split(len(group_samples))
        split_items[chosen_split].extend(group_samples)
        assigned_counts[chosen_split] += len(group_samples)

    return split_items["train"], split_items["val"], split_items["test"]


def build_segmentation_manifest(
    dataset_root: str | Path,
    *,
    metadata_path: str | Path | None = None,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    seed: int = 42,
) -> dict[str, Any]:
    samples = discover_segmentation_samples(dataset_root, metadata_path=metadata_path)
    train, val, test = grouped_train_val_test_split(
        samples,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        seed=seed,
    )
    manifest = {
        "dataset_root": str(Path(dataset_root).resolve()),
        "metadata_path": str(Path(metadata_path).resolve()) if metadata_path else None,
        "seed": seed,
        "summary": summarize_segmentation_samples(samples),
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
    manifest["summary"]["split_patients"] = {
        split_name: len({item["patient_id"] for item in manifest["splits"][split_name] if item.get("patient_id")})
        for split_name in ("train", "val", "test")
    }
    manifest["summary"]["split_lesions"] = {
        split_name: len({item["lesion_id"] for item in manifest["splits"][split_name] if item.get("lesion_id")})
        for split_name in ("train", "val", "test")
    }
    return manifest


def write_segmentation_manifest(manifest: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def crop_to_mask(
    image: np.ndarray,
    mask: np.ndarray,
    *,
    margin_ratio: float = 0.12,
    min_size: int = 48,
) -> tuple[np.ndarray, np.ndarray, tuple[int, int, int, int]]:
    if image.shape[:2] != mask.shape[:2]:
        raise ValueError("image e mask precisam ter a mesma resolucao espacial.")

    ys, xs = np.where(mask > 0)
    if len(xs) == 0 or len(ys) == 0:
        h, w = mask.shape[:2]
        return image.copy(), mask.copy(), (0, 0, w, h)

    x1, x2 = int(xs.min()), int(xs.max())
    y1, y2 = int(ys.min()), int(ys.max())
    box_w = max(x2 - x1 + 1, min_size)
    box_h = max(y2 - y1 + 1, min_size)
    margin_x = max(int(box_w * margin_ratio), 4)
    margin_y = max(int(box_h * margin_ratio), 4)

    x1 = max(0, x1 - margin_x)
    y1 = max(0, y1 - margin_y)
    x2 = min(image.shape[1], x2 + margin_x + 1)
    y2 = min(image.shape[0], y2 + margin_y + 1)

    return image[y1:y2, x1:x2].copy(), mask[y1:y2, x1:x2].copy(), (x1, y1, x2, y2)


def resize_image_and_mask(
    image: np.ndarray,
    mask: np.ndarray,
    *,
    size: int,
    image_interpolation: int = cv2.INTER_AREA,
    mask_interpolation: int = cv2.INTER_NEAREST,
) -> tuple[np.ndarray, np.ndarray]:
    resized_image = cv2.resize(image, (size, size), interpolation=image_interpolation)
    resized_mask = cv2.resize(mask, (size, size), interpolation=mask_interpolation)
    return resized_image, resized_mask
