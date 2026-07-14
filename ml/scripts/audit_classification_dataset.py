"""Audita datasets de classificacao antes de qualquer treino.

Detecta copias exatas, conflitos de rotulo e imagens visualmente muito
parecidas. O relatorio nao altera nem remove arquivos clinicos.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="dataset/medetec_consolidated")
    parser.add_argument("--output", default="ml/outputs/dataset_audits/medetec_classification_audit.json")
    parser.add_argument("--near-duplicate-distance", type=int, default=3)
    parser.add_argument("--fail-on-cross-label-conflict", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def difference_hash(image: Image.Image) -> int:
    gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    values = np.asarray(gray, dtype=np.int16)
    bits = values[:, 1:] > values[:, :-1]
    result = 0
    for bit in bits.ravel():
        result = (result << 1) | int(bit)
    return result


def label_for(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    if len(relative.parts) < 2:
        return "__unlabeled__"
    return relative.parts[0]


def scan_dataset(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    records: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    paths = sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    for path in paths:
        try:
            with Image.open(path) as image:
                width, height = image.size
                perceptual_hash = difference_hash(image)
            records.append({
                "path": str(path),
                "relative_path": str(path.relative_to(root)),
                "label": label_for(path, root),
                "sha256": sha256_file(path),
                "dhash": f"{perceptual_hash:016x}",
                "dhash_int": perceptual_hash,
                "width": width,
                "height": height,
            })
        except (OSError, UnidentifiedImageError, ValueError) as exc:
            failures.append({"path": str(path), "error": str(exc)})
    return records, failures


def audit(root: Path, near_duplicate_distance: int = 3) -> dict[str, Any]:
    records, decode_failures = scan_dataset(root)
    by_sha: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_sha[record["sha256"]].append(record)

    exact_groups = [group for group in by_sha.values() if len(group) > 1]
    conflict_groups = [group for group in exact_groups if len({item["label"] for item in group}) > 1]
    near_examples = []
    unique_records = [group[0] for group in by_sha.values()]
    for index, left in enumerate(unique_records):
        left_hash = int(left["dhash_int"])
        for right in unique_records[index + 1:]:
            if left["sha256"] == right["sha256"]:
                continue
            distance = (left_hash ^ int(right["dhash_int"])).bit_count()
            if distance <= near_duplicate_distance:
                near_examples.append({
                    "distance": distance,
                    "left": left["relative_path"],
                    "left_label": left["label"],
                    "right": right["relative_path"],
                    "right_label": right["label"],
                    "cross_label": left["label"] != right["label"],
                })

    raw_counts = Counter(record["label"] for record in records)
    unique_counts = Counter()
    for group in by_sha.values():
        labels = {item["label"] for item in group}
        if len(labels) == 1:
            unique_counts[next(iter(labels))] += 1
    return {
        "root": str(root),
        "files": len(records),
        "decodable_files": len(records),
        "decode_failures": decode_failures,
        "unique_exact_hashes": len(by_sha),
        "duplicate_groups": len(exact_groups),
        "duplicate_extra_files": sum(len(group) - 1 for group in exact_groups),
        "cross_label_exact_conflict_groups": len(conflict_groups),
        "cross_label_exact_conflict_files": sum(len(group) for group in conflict_groups),
        "class_counts_raw": dict(sorted(raw_counts.items())),
        "class_counts_unique_non_conflicting": dict(sorted(unique_counts.items())),
        "exact_conflict_examples": [
            {
                "sha256": group[0]["sha256"],
                "labels": sorted({item["label"] for item in group}),
                "paths": [item["relative_path"] for item in group],
            }
            for group in conflict_groups[:50]
        ],
        "near_duplicate_distance": near_duplicate_distance,
        "near_duplicate_pairs": len(near_examples),
        "near_duplicate_cross_label_pairs": sum(int(item["cross_label"]) for item in near_examples),
        "near_duplicate_examples": near_examples[:100],
        "patient_level_split_possible": False,
        "release_blockers": [
            blocker
            for condition, blocker in (
                (bool(decode_failures), "undecodable_images"),
                (bool(conflict_groups), "exact_images_with_conflicting_labels"),
                (len(by_sha) < len(records), "exact_duplicates_require_grouped_split"),
                (True, "patient_identifiers_unavailable_for_patient_level_split"),
            )
            if condition
        ],
    }


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    if not root.exists():
        raise SystemExit(f"Dataset nao encontrado: {root}")
    report = audit(root, args.near_duplicate_distance)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.fail_on_cross_label_conflict and report["cross_label_exact_conflict_groups"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
