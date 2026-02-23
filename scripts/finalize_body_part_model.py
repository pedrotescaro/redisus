# -*- coding: utf-8 -*-
from pathlib import Path
import json

import torch
from torch import nn
from torchvision import datasets, models

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset" / "body_parts_bootstrap"
OUT = ROOT / "models" / "body_part_detector"
OUT.mkdir(parents=True, exist_ok=True)

best_path = OUT / "body_part_detector_best.pth"
if not best_path.exists():
    raise FileNotFoundError(f"Best checkpoint não encontrado: {best_path}")

image_folder = datasets.ImageFolder(str(DATASET))
classes = image_folder.classes
num_classes = len(classes)

model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
in_features = model.classifier[-1].in_features
model.classifier[-1] = nn.Linear(in_features, num_classes)

state = torch.load(best_path, map_location="cpu")
model.load_state_dict(state)
model.eval()

full_pt = OUT / "body_part_detector_full.pt"
torch.save(model, full_pt)

meta = {
    "classes": classes,
    "num_classes": num_classes,
    "image_size": 224,
    "architecture": "mobilenet_v3_small",
    "source": "bootstrap from medetec",
}
(OUT / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

onnx_path = OUT / "body_part_detector.onnx"
dummy = torch.randn(1, 3, 224, 224)
torch.onnx.export(
    model,
    dummy,
    str(onnx_path),
    input_names=["input"],
    output_names=["logits"],
    dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
    opset_version=17,
)

print(f"OK: {full_pt}")
print(f"OK: {onnx_path}")
print(f"OK: {OUT / 'metadata.json'}")
