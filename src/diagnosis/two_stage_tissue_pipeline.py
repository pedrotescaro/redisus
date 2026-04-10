from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from ..core.config import TISSUE_NAMES, TissueType
from ..training.segmentation_dataset import crop_to_mask


@dataclass(slots=True)
class TwoStageTissuePipelineResult:
    wound_mask: np.ndarray
    tissue_mask: np.ndarray
    crop_bbox: tuple[int, int, int, int]
    wound_area_pixels: int
    tissue_percentages: dict[str, float]
    wound_result: Any = None
    tissue_result: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


class TwoStageTissuePipeline:
    """
    Pipeline em 2 estagios:
      1. Segmenta pele vs ferida
      2. Segmenta tecidos apenas dentro da ROI da ferida

    O objetivo e desacoplar a deteccao basica da lesao da leitura de tecidos.
    """

    def __init__(
        self,
        wound_segmenter: Any,
        tissue_segmenter: Any,
        *,
        crop_margin_ratio: float = 0.12,
    ):
        self.wound_segmenter = wound_segmenter
        self.tissue_segmenter = tissue_segmenter
        self.crop_margin_ratio = crop_margin_ratio

    def analyze(self, image: np.ndarray) -> TwoStageTissuePipelineResult:
        wound_result = self._call_component(self.wound_segmenter, image)
        wound_mask = self._extract_mask(wound_result, fallback_key="wound_mask")
        wound_mask = self._normalize_wound_mask(wound_mask, image.shape[:2])
        wound_area_pixels = int(np.sum(wound_mask > 0))

        if wound_area_pixels == 0:
            empty_tissue = np.zeros(image.shape[:2], dtype=np.uint8)
            return TwoStageTissuePipelineResult(
                wound_mask=wound_mask,
                tissue_mask=empty_tissue,
                crop_bbox=(0, 0, image.shape[1], image.shape[0]),
                wound_area_pixels=0,
                tissue_percentages={},
                wound_result=wound_result,
                tissue_result=None,
                metadata={"reason": "wound_mask_empty"},
            )

        crop_image, crop_mask, crop_bbox = crop_to_mask(
            image,
            wound_mask,
            margin_ratio=self.crop_margin_ratio,
        )
        tissue_result = self._call_component(self.tissue_segmenter, crop_image)
        tissue_mask_crop = self._extract_mask(tissue_result, fallback_key="mask")
        tissue_mask_crop = self._normalize_tissue_mask(tissue_mask_crop, crop_image.shape[:2])
        tissue_mask_full = np.zeros(image.shape[:2], dtype=np.uint8)

        x1, y1, x2, y2 = crop_bbox
        resized_crop = tissue_mask_crop
        if resized_crop.shape[:2] != (y2 - y1, x2 - x1):
            resized_crop = cv2.resize(
                resized_crop,
                (x2 - x1, y2 - y1),
                interpolation=cv2.INTER_NEAREST,
            )
        tissue_mask_full[y1:y2, x1:x2] = resized_crop
        tissue_mask_full[wound_mask == 0] = int(TissueType.BACKGROUND.value)

        tissue_percentages = self._calculate_tissue_percentages(tissue_mask_full, wound_mask)
        return TwoStageTissuePipelineResult(
            wound_mask=wound_mask,
            tissue_mask=tissue_mask_full,
            crop_bbox=crop_bbox,
            wound_area_pixels=wound_area_pixels,
            tissue_percentages=tissue_percentages,
            wound_result=wound_result,
            tissue_result=tissue_result,
            metadata={"crop_margin_ratio": self.crop_margin_ratio},
        )

    @staticmethod
    def _call_component(component: Any, image: np.ndarray) -> Any:
        if hasattr(component, "segment"):
            return component.segment(image)
        if hasattr(component, "analyze"):
            return component.analyze(image)
        if callable(component):
            return component(image)
        raise TypeError("Componente do pipeline precisa expor .segment(), .analyze() ou ser chamavel.")

    @staticmethod
    def _extract_mask(result: Any, *, fallback_key: str) -> np.ndarray:
        if isinstance(result, np.ndarray):
            return result
        if hasattr(result, "mask"):
            return result.mask
        if isinstance(result, dict):
            if fallback_key in result:
                return result[fallback_key]
            if "mask" in result:
                return result["mask"]
        raise ValueError("Resultado do componente nao contem mascara acessivel.")

    @staticmethod
    def _normalize_wound_mask(mask: np.ndarray, target_shape: tuple[int, int]) -> np.ndarray:
        if mask.shape[:2] != target_shape:
            mask = cv2.resize(mask, (target_shape[1], target_shape[0]), interpolation=cv2.INTER_NEAREST)
        if mask.ndim == 3:
            mask = mask[..., 0]
        return (mask > 0).astype(np.uint8) * 255

    @staticmethod
    def _normalize_tissue_mask(mask: np.ndarray, target_shape: tuple[int, int]) -> np.ndarray:
        if mask.shape[:2] != target_shape:
            mask = cv2.resize(mask, (target_shape[1], target_shape[0]), interpolation=cv2.INTER_NEAREST)
        if mask.ndim == 3:
            mask = mask[..., 0]
        return mask.astype(np.uint8)

    @staticmethod
    def _calculate_tissue_percentages(tissue_mask: np.ndarray, wound_mask: np.ndarray) -> dict[str, float]:
        wound_pixels = max(int(np.sum(wound_mask > 0)), 1)
        percentages: dict[str, float] = {}
        for class_index, class_name in TISSUE_NAMES.items():
            if class_index == int(TissueType.BACKGROUND.value):
                continue
            percentage = float(np.sum((tissue_mask == class_index) & (wound_mask > 0)) / wound_pixels * 100.0)
            if percentage > 0:
                percentages[class_name] = round(percentage, 2)
        return percentages
