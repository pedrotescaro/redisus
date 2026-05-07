"""Validate wound segmentation masks before training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="ml/datasets/manifest.jsonl")
    parser.add_argument("--min-positive-ratio", type=float, default=0.0005)
    parser.add_argument("--max-positive-ratio", type=float, default=0.80)
    return parser.parse_args()


def load_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    args = parse_args()
    records = load_records(Path(args.manifest))
    try:
        from PIL import Image
        import numpy as np
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"Pillow e numpy sao necessarios para validar mascaras: {exc}") from exc

    failures: list[dict] = []
    for record in records:
        image_path = Path(record["image"])
        mask_path = Path(record["mask"])
        if not image_path.exists() or not mask_path.exists():
            failures.append({"id": record.get("id"), "error": "missing_file"})
            continue

        with Image.open(image_path) as image, Image.open(mask_path) as mask:
            if image.size != mask.size:
                failures.append({"id": record.get("id"), "error": "size_mismatch", "image": image.size, "mask": mask.size})
                continue
            mask_array = np.asarray(mask.convert("L"))
            positive_ratio = float((mask_array > 0).mean())
            if positive_ratio < args.min_positive_ratio:
                failures.append({"id": record.get("id"), "error": "mask_too_small", "positive_ratio": positive_ratio})
            if positive_ratio > args.max_positive_ratio:
                failures.append({"id": record.get("id"), "error": "mask_too_large", "positive_ratio": positive_ratio})

    print(json.dumps({
        "records": len(records),
        "failures": len(failures),
        "failure_examples": failures[:20]
    }, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
