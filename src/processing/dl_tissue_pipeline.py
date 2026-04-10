# -*- coding: utf-8 -*-
"""Deep Learning tissue pipeline for the ClinicalWoundAnalyzer.

Two-stage inference:
  1. Wound-mask segmentation (DeepLabV3-ResNet50, binary) — isolates the wound ROI
  2. Tissue segmentation (DeepLabV3-ResNet50, 5-class) — classifies tissues inside the cropped ROI

When both models are available the pipeline replaces the heuristic HSV/LAB
tissue classification used by ``_segment_clinical_v3``.  When models are
missing the pipeline raises ``DLPipelineUnavailable`` so the caller can
fall back transparently.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

LEGACY_ROOT = Path(__file__).resolve().parents[2]

# Default model directories (match training output paths)
WOUND_MASK_MODEL_DIR = LEGACY_ROOT / "models" / "wound_mask_deeplabv3"
WOUND_MASK_CHECKPOINT = "wound_mask_deeplabv3_384.pth"

TISSUE_SEG_MODEL_DIR = LEGACY_ROOT / "models" / "tissue_segmentation_deeplabv3"
TISSUE_SEG_CHECKPOINT = "tissue_segmentation_deeplabv3_384.pth"

# Tissue class mapping (from src.core.config.TissueType)
#   0 = Background, 1 = Granulation, 2 = Slough, 3 = Necrosis, 4 = Periwound
# The ClinicalWoundAnalyzer uses 4 clinical tissue keys:
#   necrosis, slough, granulation, epithelialization
# Mapping: periwound → excluded (not wound tissue), epithelialization is
# detected separately via gradient analysis on the peripheral zone.
DL_CLASS_TO_CLINICAL = {
    1: "granulation",
    2: "slough",
    3: "necrosis",
    # 4 (periwound) is excluded from wound tissue percentages
}

# Colors for tissue overlay (BGR, matching ClinicalWoundAnalyzer conventions)
TISSUE_OVERLAY_COLORS = {
    "necrosis": (30, 30, 60),
    "slough": (80, 220, 220),
    "granulation": (60, 60, 220),
    "epithelialization": (200, 180, 255),
}


class DLPipelineUnavailable(Exception):
    """Raised when DL models are not available for inference."""


@dataclass
class DLTissuePipelineResult:
    """Result from the DL tissue pipeline."""
    wound_mask: np.ndarray            # uint8, 0/255 binary mask
    tissue_mask: np.ndarray           # uint8, indexed [0..4] on full image
    tissue_percentages: Dict[str, float]  # clinical keys → percentage
    seg_map: np.ndarray               # BGR color-coded segmentation map
    tissue_overlay: np.ndarray        # original blended with seg_map
    crop_bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2) of the crop
    wound_area_pixels: int
    inference_time_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class _DeepLabV3Inference:
    """Lightweight wrapper for a DeepLabV3-ResNet50 checkpoint (state_dict)."""

    def __init__(
        self,
        checkpoint_path: Path,
        num_classes: int,
        input_size: int = 384,
        threshold: float = 0.5,
    ):
        self._checkpoint_path = checkpoint_path
        self._num_classes = num_classes
        self._input_size = input_size
        self._threshold = threshold
        self._model = None
        self._device = None
        self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def load(self) -> bool:
        """Attempt to load the model. Returns True on success."""
        if not self._checkpoint_path.exists():
            logger.info(
                "[DL-Pipeline] Checkpoint não encontrado: %s", self._checkpoint_path
            )
            return False
        try:
            import torch
            from torchvision import models as tv_models

            self._device = torch.device(
                "cuda" if torch.cuda.is_available() else "cpu"
            )

            # Build architecture
            model = tv_models.segmentation.deeplabv3_resnet50(
                num_classes=self._num_classes,
            )
            # Load weights from checkpoint
            ckpt = torch.load(
                str(self._checkpoint_path),
                map_location=self._device,
                weights_only=False,
            )
            state_dict = ckpt.get("model_state_dict", ckpt)
            model.load_state_dict(state_dict)
            model.to(self._device).eval()
            self._model = model
            self._available = True
            logger.info(
                "[DL-Pipeline] Modelo carregado: %s (%s)",
                self._checkpoint_path.name,
                self._device,
            )
            return True
        except Exception as exc:
            logger.warning(
                "[DL-Pipeline] Falha ao carregar %s: %s",
                self._checkpoint_path.name,
                exc,
            )
            return False

    def predict(self, image_rgb: np.ndarray) -> np.ndarray:
        """Run inference on a single RGB image.

        Args:
            image_rgb: H×W×3 uint8 RGB image.

        Returns:
            For binary (num_classes=1): H×W uint8 mask (0/255).
            For multiclass: H×W uint8 class indices.
        """
        if not self._available or self._model is None:
            raise DLPipelineUnavailable("Modelo não carregado")

        import torch

        h_orig, w_orig = image_rgb.shape[:2]

        # Resize to model input
        resized = cv2.resize(
            image_rgb, (self._input_size, self._input_size),
            interpolation=cv2.INTER_AREA,
        )
        # Normalize [0,1] and transpose to CHW
        tensor = resized.astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))  # (3, H, W)
        tensor = torch.from_numpy(tensor).unsqueeze(0).to(self._device)

        with torch.no_grad():
            output = self._model(tensor)["out"]  # (1, C, H, W)

            if self._num_classes == 1:
                # Binary segmentation
                prob = output.sigmoid().squeeze(0).squeeze(0).cpu().numpy()
                mask_small = (prob >= self._threshold).astype(np.uint8) * 255
            else:
                # Multi-class segmentation
                mask_small = output.argmax(dim=1).squeeze(0).cpu().numpy().astype(np.uint8)

        # Resize back to original resolution
        mask_full = cv2.resize(
            mask_small, (w_orig, h_orig), interpolation=cv2.INTER_NEAREST,
        )
        return mask_full


class DLTissuePipeline:
    """Two-stage DL pipeline: wound-mask → crop → tissue segmentation.

    Usage::

        pipeline = DLTissuePipeline()
        if pipeline.available:
            result = pipeline.analyze(image_bgr)
    """

    def __init__(
        self,
        wound_mask_dir: Optional[Path] = None,
        tissue_seg_dir: Optional[Path] = None,
        *,
        input_size: int = 384,
        crop_margin_ratio: float = 0.12,
        wound_threshold: float = 0.5,
    ):
        wound_dir = wound_mask_dir or WOUND_MASK_MODEL_DIR
        tissue_dir = tissue_seg_dir or TISSUE_SEG_MODEL_DIR

        self._wound_model = _DeepLabV3Inference(
            checkpoint_path=wound_dir / WOUND_MASK_CHECKPOINT,
            num_classes=1,
            input_size=input_size,
            threshold=wound_threshold,
        )
        self._tissue_model = _DeepLabV3Inference(
            checkpoint_path=tissue_dir / TISSUE_SEG_CHECKPOINT,
            num_classes=5,
            input_size=input_size,
        )
        self._crop_margin_ratio = crop_margin_ratio
        self._input_size = input_size
        self._available = False
        self._load()

    def _load(self) -> None:
        wound_ok = self._wound_model.load()
        tissue_ok = self._tissue_model.load()
        self._available = wound_ok and tissue_ok
        if self._available:
            print(
                f"[HEAL+] DL Tissue Pipeline: wound-mask ✓, tissue-seg ✓ "
                f"(input={self._input_size}px)"
            )
        else:
            reasons = []
            if not wound_ok:
                reasons.append("wound-mask")
            if not tissue_ok:
                reasons.append("tissue-seg")
            print(
                f"[HEAL+] DL Tissue Pipeline indisponível "
                f"(modelos faltando: {', '.join(reasons)}). Usando heurística."
            )

    @property
    def available(self) -> bool:
        return self._available

    def analyze(
        self,
        image_bgr: np.ndarray,
        *,
        epi_mask: Optional[np.ndarray] = None,
    ) -> DLTissuePipelineResult:
        """Run the full two-stage DL pipeline.

        Args:
            image_bgr: Original BGR image.
            epi_mask: Optional epithelialization mask (uint8, 0/255) from
                gradient-based detector. If provided, it is blended into the
                tissue percentages.

        Returns:
            DLTissuePipelineResult with wound mask, tissue mask, percentages,
            and visual overlays.

        Raises:
            DLPipelineUnavailable: If models are not loaded.
        """
        if not self._available:
            raise DLPipelineUnavailable("Pipeline DL não disponível")

        t0 = time.perf_counter()

        # Convert to RGB for model inference
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

        # --- Stage 1: Wound mask ---
        wound_mask = self._wound_model.predict(image_rgb)  # uint8, 0/255
        wound_area = int(np.sum(wound_mask > 0))

        h, w = image_bgr.shape[:2]

        if wound_area == 0:
            # No wound detected — return empty result
            empty = np.zeros((h, w), dtype=np.uint8)
            return DLTissuePipelineResult(
                wound_mask=wound_mask,
                tissue_mask=empty,
                tissue_percentages={},
                seg_map=np.full((h, w, 3), 80, dtype=np.uint8),
                tissue_overlay=image_bgr.copy(),
                crop_bbox=(0, 0, w, h),
                wound_area_pixels=0,
                inference_time_ms=(time.perf_counter() - t0) * 1000,
                metadata={"reason": "wound_mask_empty"},
            )

        # --- Crop to wound ROI ---
        crop_image, crop_mask, crop_bbox = self._crop_to_mask(
            image_rgb, wound_mask, margin_ratio=self._crop_margin_ratio,
        )

        # --- Stage 2: Tissue segmentation on cropped region ---
        tissue_mask_crop = self._tissue_model.predict(crop_image)  # uint8, [0..4]

        # Project crop back to full image
        tissue_mask_full = np.zeros((h, w), dtype=np.uint8)
        x1, y1, x2, y2 = crop_bbox
        crop_h, crop_w = y2 - y1, x2 - x1
        if tissue_mask_crop.shape[:2] != (crop_h, crop_w):
            tissue_mask_crop = cv2.resize(
                tissue_mask_crop, (crop_w, crop_h),
                interpolation=cv2.INTER_NEAREST,
            )
        tissue_mask_full[y1:y2, x1:x2] = tissue_mask_crop
        # Zero out areas outside wound mask
        tissue_mask_full[wound_mask == 0] = 0

        # --- Calculate clinical tissue percentages ---
        tissue_pcts = self._calculate_tissue_percentages(
            tissue_mask_full, wound_mask, epi_mask=epi_mask,
        )

        # --- Build visual overlays ---
        seg_map, tissue_overlay = self._build_overlays(
            image_bgr, tissue_mask_full, wound_mask, epi_mask=epi_mask,
        )

        inference_ms = (time.perf_counter() - t0) * 1000

        return DLTissuePipelineResult(
            wound_mask=wound_mask,
            tissue_mask=tissue_mask_full,
            tissue_percentages=tissue_pcts,
            seg_map=seg_map,
            tissue_overlay=tissue_overlay,
            crop_bbox=crop_bbox,
            wound_area_pixels=wound_area,
            inference_time_ms=inference_ms,
            metadata={
                "pipeline": "dl_two_stage",
                "wound_model": WOUND_MASK_CHECKPOINT,
                "tissue_model": TISSUE_SEG_CHECKPOINT,
                "input_size": self._input_size,
                "crop_margin_ratio": self._crop_margin_ratio,
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _crop_to_mask(
        image: np.ndarray,
        mask: np.ndarray,
        *,
        margin_ratio: float = 0.12,
        min_size: int = 48,
    ) -> Tuple[np.ndarray, np.ndarray, Tuple[int, int, int, int]]:
        """Crop image and mask to the bounding box of nonzero mask pixels.

        Replicates ``segmentation_dataset.crop_to_mask`` without importing
        the training module at runtime.
        """
        ys, xs = np.where(mask > 0)
        if len(xs) == 0 or len(ys) == 0:
            h, w = mask.shape[:2]
            return image.copy(), mask.copy(), (0, 0, w, h)

        x1_raw, x2_raw = int(xs.min()), int(xs.max())
        y1_raw, y2_raw = int(ys.min()), int(ys.max())
        box_w = max(x2_raw - x1_raw + 1, min_size)
        box_h = max(y2_raw - y1_raw + 1, min_size)
        margin_x = max(int(box_w * margin_ratio), 4)
        margin_y = max(int(box_h * margin_ratio), 4)

        x1 = max(0, x1_raw - margin_x)
        y1 = max(0, y1_raw - margin_y)
        x2 = min(image.shape[1], x2_raw + margin_x + 1)
        y2 = min(image.shape[0], y2_raw + margin_y + 1)

        return image[y1:y2, x1:x2].copy(), mask[y1:y2, x1:x2].copy(), (x1, y1, x2, y2)

    @staticmethod
    def _calculate_tissue_percentages(
        tissue_mask: np.ndarray,
        wound_mask: np.ndarray,
        *,
        epi_mask: Optional[np.ndarray] = None,
    ) -> Dict[str, float]:
        """Map DL class indices to clinical tissue percentages."""
        wound_pixels = max(int(np.sum(wound_mask > 0)), 1)

        pcts: Dict[str, float] = {
            "necrosis": 0.0,
            "slough": 0.0,
            "granulation": 0.0,
            "epithelialization": 0.0,
        }

        for class_idx, clinical_key in DL_CLASS_TO_CLINICAL.items():
            count = int(np.sum(
                (tissue_mask == class_idx) & (wound_mask > 0)
            ))
            pcts[clinical_key] = float(count / wound_pixels * 100.0)

        # Blend in epithelialization from gradient detector
        if epi_mask is not None:
            epi_pixels = int(np.sum(
                (epi_mask > 0) & (wound_mask > 0)
            ))
            epi_pct = float(epi_pixels / wound_pixels * 100.0)
            # Epithelialization takes pixels from other tissues proportionally
            if epi_pct > 0:
                pcts["epithelialization"] = epi_pct
                # Deduct proportionally from existing tissues
                total_other = sum(
                    v for k, v in pcts.items() if k != "epithelialization"
                )
                if total_other > 0:
                    scale = max(0, (total_other - epi_pct)) / total_other
                    for key in ("necrosis", "slough", "granulation"):
                        pcts[key] *= scale

        return pcts

    @staticmethod
    def _build_overlays(
        image_bgr: np.ndarray,
        tissue_mask: np.ndarray,
        wound_mask: np.ndarray,
        *,
        epi_mask: Optional[np.ndarray] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Build seg_map and tissue_overlay for ClinicalReport."""
        h, w = image_bgr.shape[:2]
        seg_map = np.full((h, w, 3), 80, dtype=np.uint8)

        # Paint DL tissue classes
        for class_idx, clinical_key in DL_CLASS_TO_CLINICAL.items():
            color = TISSUE_OVERLAY_COLORS.get(clinical_key, (128, 128, 128))
            seg_map[tissue_mask == class_idx] = color

        # Paint epithelialization from gradient detector
        if epi_mask is not None:
            color = TISSUE_OVERLAY_COLORS["epithelialization"]
            seg_map[epi_mask > 0] = color

        # Blend overlay
        overlay = image_bgr.copy()
        cv2.addWeighted(seg_map, 0.45, overlay, 0.55, 0, overlay)

        # Draw wound mask contour
        contours, _ = cv2.findContours(
            wound_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )
        cv2.drawContours(overlay, contours, -1, (0, 255, 0), 2)

        return seg_map, overlay
