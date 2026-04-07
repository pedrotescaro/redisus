"""Download pretrained model weights."""
from pathlib import Path

import timm

ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT_DIR / "artifacts" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

print("Downloading mobilenetv3_large_100...")
m = timm.create_model("mobilenetv3_large_100", pretrained=True, num_classes=0)
print(f"Downloaded OK, features: {m.num_features}")
with open(LOG_DIR / "download_done.txt", "w", encoding="utf-8") as f:
    f.write("ok")
