"""Runtime seguro para segmentacao binaria de feridas.

O mesmo modelo e o mesmo redimensionamento sao reutilizados pelo treino e pela
inferencia. O preditor nunca transforma probabilidade de pixel em certeza
clinica: ele pode abster-se e devolver a ROI original para revisao humana.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image


MODEL_ARCHITECTURE = "small_unet_gn_v2"


class ConvBlock(nn.Module):
    """Bloco convolucional estavel mesmo com batches clinicos pequenos."""

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        groups = min(8, out_channels)
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.GroupNorm(groups, out_channels),
            nn.SiLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.GroupNorm(groups, out_channels),
            nn.SiLU(inplace=True),
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.block(value)


class SmallUNet(nn.Module):
    """U-Net compacta para segmentacao ferida versus fundo."""

    def __init__(self, base_channels: int = 16):
        super().__init__()
        c1, c2, c3, c4 = (base_channels * factor for factor in (1, 2, 4, 8))
        self.base_channels = base_channels
        self.enc1 = ConvBlock(3, c1)
        self.enc2 = ConvBlock(c1, c2)
        self.enc3 = ConvBlock(c2, c3)
        self.pool = nn.MaxPool2d(2)
        self.bottleneck = ConvBlock(c3, c4)
        self.up3 = nn.ConvTranspose2d(c4, c3, kernel_size=2, stride=2)
        self.dec3 = ConvBlock(c3 * 2, c3)
        self.up2 = nn.ConvTranspose2d(c3, c2, kernel_size=2, stride=2)
        self.dec2 = ConvBlock(c2 * 2, c2)
        self.up1 = nn.ConvTranspose2d(c2, c1, kernel_size=2, stride=2)
        self.dec1 = ConvBlock(c1 * 2, c1)
        self.head = nn.Conv2d(c1, 1, kernel_size=1)

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        enc1 = self.enc1(image)
        enc2 = self.enc2(self.pool(enc1))
        enc3 = self.enc3(self.pool(enc2))
        bottleneck = self.bottleneck(self.pool(enc3))
        dec3 = self.dec3(torch.cat([self.up3(bottleneck), enc3], dim=1))
        dec2 = self.dec2(torch.cat([self.up2(dec3), enc2], dim=1))
        dec1 = self.dec1(torch.cat([self.up1(dec2), enc1], dim=1))
        return self.head(dec1)


@dataclass(frozen=True)
class LetterboxMetadata:
    original_width: int
    original_height: int
    resized_width: int
    resized_height: int
    offset_x: int
    offset_y: int
    canvas_size: int


def letterbox_pil(
    image: Image.Image,
    size: int,
    *,
    resample: Image.Resampling,
    fill: int | tuple[int, int, int] = 0,
) -> tuple[Image.Image, LetterboxMetadata]:
    """Redimensiona sem deformar a geometria e adiciona padding central."""

    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError("Imagem sem dimensoes validas.")
    scale = min(size / width, size / height)
    resized_width = max(1, min(size, round(width * scale)))
    resized_height = max(1, min(size, round(height * scale)))
    resized = image.resize((resized_width, resized_height), resample)
    mode = image.mode
    canvas = Image.new(mode, (size, size), fill)
    offset_x = (size - resized_width) // 2
    offset_y = (size - resized_height) // 2
    canvas.paste(resized, (offset_x, offset_y))
    return canvas, LetterboxMetadata(
        original_width=width,
        original_height=height,
        resized_width=resized_width,
        resized_height=resized_height,
        offset_x=offset_x,
        offset_y=offset_y,
        canvas_size=size,
    )


def undo_letterbox(array: np.ndarray, metadata: LetterboxMetadata, *, interpolation: int) -> np.ndarray:
    """Remove o padding e restaura a resolucao original."""

    y1 = metadata.offset_y
    y2 = y1 + metadata.resized_height
    x1 = metadata.offset_x
    x2 = x1 + metadata.resized_width
    cropped = array[y1:y2, x1:x2]
    return cv2.resize(
        cropped,
        (metadata.original_width, metadata.original_height),
        interpolation=interpolation,
    )


@dataclass
class WoundSegmentationPrediction:
    mask: np.ndarray
    probability_map: np.ndarray
    accepted: bool
    reason: str
    threshold: float
    foreground_confidence: float
    coverage_ratio: float
    mean_entropy: float
    model_architecture: str
    model_version: str
    checkpoint_epoch: int | None
    clinical_status: str

    def metadata(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("mask")
        payload.pop("probability_map")
        return payload


def _binary_entropy(probabilities: np.ndarray) -> np.ndarray:
    clipped = np.clip(probabilities, 1e-6, 1 - 1e-6)
    return -(
        clipped * np.log2(clipped)
        + (1 - clipped) * np.log2(1 - clipped)
    )


def clean_binary_mask(mask: np.ndarray, *, min_component_ratio: float = 0.0005) -> np.ndarray:
    """Remove ruido isolado sem apagar multiplas feridas relevantes."""

    binary = (mask > 0).astype(np.uint8)
    kernel = np.ones((3, 3), dtype=np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    minimum_area = max(16, round(binary.size * min_component_ratio))
    cleaned = np.zeros_like(binary)
    for component in range(1, count):
        if int(stats[component, cv2.CC_STAT_AREA]) >= minimum_area:
            cleaned[labels == component] = 1
    return cleaned * 255


class WoundSegmentationPredictor:
    """Carrega checkpoint rastreavel e produz mascara com opcao de abstencao."""

    def __init__(
        self,
        checkpoint_path: str | Path,
        *,
        device: Literal["auto", "cpu", "cuda"] = "auto",
        allow_non_commercial_research: bool = False,
    ):
        self.checkpoint_path = Path(checkpoint_path)
        if not self.checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint nao encontrado: {self.checkpoint_path}")
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA solicitada, mas indisponivel.")
        self.device = torch.device(
            "cuda" if device == "auto" and torch.cuda.is_available() else "cpu" if device == "auto" else device
        )
        checkpoint = torch.load(self.checkpoint_path, map_location=self.device, weights_only=True)
        license_scope = str(checkpoint.get("license_scope", "unknown"))
        if "non_commercial" in license_scope and not allow_non_commercial_research:
            raise PermissionError(
                "Checkpoint restrito a pesquisa nao comercial. "
                "Habilite-o somente apos revisar os termos do dataset."
            )
        architecture = str(checkpoint.get("architecture", checkpoint.get("model", "")))
        if architecture not in {MODEL_ARCHITECTURE, "SmallUNet"}:
            raise ValueError(f"Arquitetura de checkpoint nao suportada: {architecture!r}")
        base_channels = int(checkpoint.get("base_channels", 16 if architecture == MODEL_ARCHITECTURE else 32))
        self.model = SmallUNet(base_channels=base_channels).to(self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()
        args = checkpoint.get("training_args", {})
        self.image_size = int(args.get("image_size", checkpoint.get("image_size", 256)))
        self.threshold = float(checkpoint.get("decision_threshold", 0.5))
        self.model_version = str(checkpoint.get("model_version", f"epoch-{checkpoint.get('epoch', 'unknown')}"))
        self.checkpoint_epoch = int(checkpoint["epoch"]) if checkpoint.get("epoch") is not None else None
        self.clinical_status = str(checkpoint.get("clinical_status", "experimental_not_clinically_validated"))
        self.license_scope = license_scope

    def predict(
        self,
        image: np.ndarray,
        *,
        color_order: Literal["bgr", "rgb"] = "bgr",
        roi_mask: np.ndarray | None = None,
        min_foreground_confidence: float = 0.60,
        min_coverage_ratio: float = 0.002,
        max_coverage_ratio: float = 0.95,
    ) -> WoundSegmentationPrediction:
        if image is None or image.ndim != 3 or image.shape[2] != 3 or image.size == 0:
            raise ValueError("Imagem RGB/BGR invalida.")
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if color_order == "bgr" else image
        pil_image = Image.fromarray(rgb.astype(np.uint8), mode="RGB")
        prepared, metadata = letterbox_pil(
            pil_image,
            self.image_size,
            resample=Image.Resampling.BILINEAR,
            fill=(0, 0, 0),
        )
        image_array = np.asarray(prepared, dtype=np.float32) / 255.0
        tensor = torch.from_numpy(image_array.transpose(2, 0, 1)).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            probabilities_small = torch.sigmoid(self.model(tensor))[0, 0].cpu().numpy()
        probabilities = undo_letterbox(probabilities_small, metadata, interpolation=cv2.INTER_LINEAR)

        valid_region = np.ones(probabilities.shape, dtype=bool)
        if roi_mask is not None:
            normalized_roi = cv2.resize(
                (roi_mask > 0).astype(np.uint8),
                (probabilities.shape[1], probabilities.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            )
            valid_region = normalized_roi > 0
            probabilities = np.where(valid_region, probabilities, 0.0)

        raw_mask = (probabilities >= self.threshold).astype(np.uint8) * 255
        mask = clean_binary_mask(raw_mask)
        foreground = mask > 0
        denominator = max(int(valid_region.sum()), 1)
        coverage_ratio = float(foreground.sum() / denominator)
        foreground_confidence = float(probabilities[foreground].mean()) if foreground.any() else 0.0
        entropy_values = _binary_entropy(probabilities[valid_region])
        mean_entropy = float(entropy_values.mean()) if entropy_values.size else 1.0

        accepted = True
        reason = "accepted"
        if not foreground.any() or coverage_ratio < min_coverage_ratio:
            accepted = False
            reason = "predicted_wound_too_small_or_empty"
        elif coverage_ratio > max_coverage_ratio:
            accepted = False
            reason = "predicted_wound_too_large"
        elif foreground_confidence < min_foreground_confidence:
            accepted = False
            reason = "low_foreground_confidence"

        return WoundSegmentationPrediction(
            mask=mask,
            probability_map=probabilities.astype(np.float32),
            accepted=accepted,
            reason=reason,
            threshold=self.threshold,
            foreground_confidence=round(foreground_confidence, 6),
            coverage_ratio=round(coverage_ratio, 6),
            mean_entropy=round(mean_entropy, 6),
            model_architecture=MODEL_ARCHITECTURE,
            model_version=self.model_version,
            checkpoint_epoch=self.checkpoint_epoch,
            clinical_status=self.clinical_status,
        )


def checkpoint_metadata(checkpoint_path: str | Path) -> dict[str, Any]:
    """Le metadados sem inicializar o modelo."""

    checkpoint = torch.load(Path(checkpoint_path), map_location="cpu", weights_only=True)
    return {
        "architecture": checkpoint.get("architecture", checkpoint.get("model")),
        "model_version": checkpoint.get("model_version"),
        "epoch": checkpoint.get("epoch"),
        "best_epoch": checkpoint.get("best_epoch"),
        "best_dice": checkpoint.get("best_dice"),
        "decision_threshold": checkpoint.get("decision_threshold", 0.5),
        "clinical_status": checkpoint.get("clinical_status"),
        "license_scope": checkpoint.get("license_scope"),
        "dataset": checkpoint.get("dataset"),
    }
