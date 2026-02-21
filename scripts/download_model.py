"""Download pretrained model weights."""
import timm
print("Downloading mobilenetv3_large_100...")
m = timm.create_model("mobilenetv3_large_100", pretrained=True, num_classes=0)
print(f"Downloaded OK, features: {m.num_features}")
with open("download_done.txt", "w") as f:
    f.write("ok")
