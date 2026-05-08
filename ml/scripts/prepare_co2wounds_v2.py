"""Prepare CO2Wounds-V2 manifests for experimental wound segmentation.

The script expects the dataset to be downloaded manually after reviewing the
Mendeley/IEEE/GitHub terms. It supports the split layout used by the official
benchmark (`train`, `train_anns`, `val`, `val_anns`, optional `test`) and a
COCO-style fallback (`annotations/*.json` + `imgs/`).
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


DATASET_NAME = "CO2Wounds-V2"
DATASET_LICENSE = "CC BY-NC 3.0 on Mendeley v2; GitHub benchmark states CC BY-NC-ND"
DATASET_DOI = "10.17632/s2w7rjwz49.2"
PAPER_DOI = "10.1109/ICIP51287.2024.10647641"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="data/external/co2wounds-v2")
    parser.add_argument("--output-dir", default="ml/datasets")
    parser.add_argument("--val-ratio", type=float, default=0.20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--accept-non-commercial-research-license", action="store_true")
    return parser.parse_args()


def require_license_acceptance(accepted: bool) -> None:
    if accepted:
        return
    raise SystemExit(
        "CO2Wounds-V2 tem restricao nao comercial e possivel restricao ND. "
        "Reveja a licenca e rode novamente com --accept-non-commercial-research-license "
        "somente para uso academico/experimental."
    )


def image_files(root: Path) -> list[Path]:
    supported = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in supported)


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def paired_split_records(root: Path, split: str) -> list[dict[str, Any]]:
    image_dir = root / split
    mask_dir = root / f"{split}_anns"
    if not image_dir.exists() or not mask_dir.exists():
        return []

    masks_by_stem = {path.stem: path for path in image_files(mask_dir)}
    records: list[dict[str, Any]] = []
    for image_path in image_files(image_dir):
        mask_path = masks_by_stem.get(image_path.stem)
        if mask_path is None:
            continue
        records.append(base_record(image_path.stem, image_path, mask_path, split))
    return records


def base_record(record_id: str, image_path: Path, mask_path: Path | None, split: str) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": record_id,
        "image": str(image_path),
        "dataset": DATASET_NAME,
        "license": DATASET_LICENSE,
        "dataset_doi": DATASET_DOI,
        "paper_doi": PAPER_DOI,
        "split": split,
        "label": "wound_area",
        "deidentified": True,
        "use_scope": "academic_research_prototype_only",
        "commercial_use_allowed": False,
        "model_output_allowed": "experimental_segmentation_only"
    }
    if mask_path is not None:
        record["mask"] = str(mask_path)
    return record


def draw_coco_mask(
    *,
    annotations: list[dict[str, Any]],
    width: int,
    height: int,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    for annotation in annotations:
        segmentation = annotation.get("segmentation")
        if not isinstance(segmentation, list):
            continue
        for polygon in segmentation:
            if not isinstance(polygon, list) or len(polygon) < 6:
                continue
            points = [(float(polygon[index]), float(polygon[index + 1])) for index in range(0, len(polygon) - 1, 2)]
            draw.polygon(points, fill=255)
    mask.save(output_path)
    return output_path


def coco_records(
    root: Path,
    val_ratio: float,
    seed: int,
    *,
    generated_mask_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    annotations_dir = root / "annotations"
    image_dir = root / "imgs"
    if not annotations_dir.exists() or not image_dir.exists():
        return [], []

    annotation_files = sorted(annotations_dir.glob("*.json"))
    if not annotation_files:
        return [], []

    annotation_path = next((path for path in annotation_files if "merged" in path.name.lower()), annotation_files[0])
    payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    images = payload.get("images", [])
    annotations_by_image_id: dict[Any, list[dict[str, Any]]] = {}
    for annotation in payload.get("annotations", []):
        annotations_by_image_id.setdefault(annotation.get("image_id"), []).append(annotation)

    image_records = []
    for item in images:
        filename = item.get("file_name")
        if not filename:
            continue
        image_path = image_dir / str(filename)
        image_id = item.get("id")
        annotations = annotations_by_image_id.get(image_id, [])
        if image_path.exists() and annotations:
            if item.get("width") and item.get("height"):
                width = int(item["width"])
                height = int(item["height"])
            else:
                with Image.open(image_path) as image:
                    width, height = image.size
            mask_path = draw_coco_mask(
                annotations=annotations,
                width=width,
                height=height,
                output_path=generated_mask_dir / f"{image_path.stem}.png",
            )
            image_records.append(base_record(str(image_id or image_path.stem), image_path, mask_path, "unsplit_coco"))

    random.Random(seed).shuffle(image_records)
    val_count = max(1, int(len(image_records) * val_ratio)) if image_records else 0
    val_records = image_records[:val_count]
    train_records = image_records[val_count:]
    for record in train_records:
        record["split"] = "train"
        record["coco_annotations"] = str(annotation_path)
    for record in val_records:
        record["split"] = "val"
        record["coco_annotations"] = str(annotation_path)
    return train_records, val_records


def main() -> None:
    args = parse_args()
    require_license_acceptance(args.accept_non_commercial_research_license)

    root = Path(args.root)
    output_dir = Path(args.output_dir)
    if not root.exists():
        raise SystemExit(
            f"Dataset nao encontrado em {root}. Baixe o CO2Wounds-V2 manualmente "
            "a partir do Mendeley/IEEE DataPort apos revisar os termos."
        )

    train_records = paired_split_records(root, "train")
    val_records = paired_split_records(root, "val")
    test_records = [base_record(path.stem, path, None, "unlabeled_test") for path in image_files(root / "test")] if (root / "test").exists() else []

    if not train_records or not val_records:
        train_records, val_records = coco_records(
            root,
            args.val_ratio,
            args.seed,
            generated_mask_dir=output_dir / "co2wounds_v2_generated_masks",
        )

    if not train_records or not val_records:
        raise SystemExit(
            "Nao foi possivel localizar imagens e mascaras do CO2Wounds-V2. "
            "Use o layout oficial data/CO2wounds/{train,train_anns,val,val_anns} "
            "ou data/CO2wounds/{annotations/merged_annotations.json,imgs/}."
        )

    write_jsonl(output_dir / "co2wounds_v2_train.jsonl", train_records)
    write_jsonl(output_dir / "co2wounds_v2_val.jsonl", val_records)
    write_jsonl(output_dir / "co2wounds_v2_unlabeled_test.jsonl", test_records)

    dataset_card = {
        "dataset": DATASET_NAME,
        "dataset_doi": DATASET_DOI,
        "paper_doi": PAPER_DOI,
        "license": DATASET_LICENSE,
        "use_scope": "academic_research_prototype_only",
        "commercial_use_allowed": False,
        "train_records": len(train_records),
        "val_records": len(val_records),
        "unlabeled_test_records": len(test_records),
        "requires_note": "Modelo resultante e experimental e nao deve ser apresentado como IA clinica validada."
    }
    (output_dir / "co2wounds_v2_dataset_card.json").write_text(json.dumps(dataset_card, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(dataset_card, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
