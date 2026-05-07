"""Prepare a licensed wound segmentation manifest.

This script does not download restricted datasets. Point it at a dataset that
has already passed license, consent and de-identification review.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", required=True, help="Directory containing RGB images.")
    parser.add_argument("--masks", required=True, help="Directory containing binary masks.")
    parser.add_argument("--output", default="ml/datasets/manifest.jsonl")
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--license", required=True)
    parser.add_argument("--split", default="unsplit")
    return parser.parse_args()


def collect_files(root: Path) -> dict[str, Path]:
    supported = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    return {
        path.stem: path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in supported
    }


def main() -> None:
    args = parse_args()
    image_root = Path(args.images)
    mask_root = Path(args.masks)
    output = Path(args.output)

    images = collect_files(image_root)
    masks = collect_files(mask_root)
    missing_masks = sorted(set(images) - set(masks))
    paired_keys = sorted(set(images) & set(masks))

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for key in paired_keys:
            record = {
                "id": key,
                "image": str(images[key]),
                "mask": str(masks[key]),
                "dataset": args.dataset_name,
                "license": args.license,
                "split": args.split,
                "label": "wound_area",
                "deidentified": True,
                "professional_mask_review": "source_dataset_or_pending"
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(json.dumps({
        "output": str(output),
        "paired": len(paired_keys),
        "missing_masks": len(missing_masks),
        "missing_mask_examples": missing_masks[:10]
    }, indent=2))


if __name__ == "__main__":
    main()
