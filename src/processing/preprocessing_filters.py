# -*- coding: utf-8 -*-
"""Experimental OpenCV preprocessing filters for wound images.

These helpers are intentionally separate from the production analysis path.
They support comparative experiments requested for HEAL+ / REDISUS without
making any filter mandatory before clinical validation.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

ImageTransform = Callable[[np.ndarray], np.ndarray]

SUPPORTED_IMAGE_EXTENSIONS = {
    ".bmp",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}


def _ensure_odd_positive(value: int, *, name: str) -> int:
    if value <= 0 or value % 2 == 0:
        raise ValueError(f"{name} must be a positive odd integer.")
    return value


def _ensure_odd_kernel(ksize: tuple[int, int]) -> tuple[int, int]:
    if len(ksize) != 2:
        raise ValueError("ksize must contain exactly two integers.")
    return (
        _ensure_odd_positive(int(ksize[0]), name="ksize[0]"),
        _ensure_odd_positive(int(ksize[1]), name="ksize[1]"),
    )


def load_image_bgr(path: str | Path) -> np.ndarray:
    """Load an image with OpenCV preserving the BGR convention used locally."""
    image_path = Path(path)
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")
    return image


def save_image(path: str | Path, image: np.ndarray) -> None:
    """Save an image and create parent directories when needed."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), image):
        raise OSError(f"Could not save image: {output_path}")


def bgr_to_rgb(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def rgb_to_bgr(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)


def ensure_bgr_for_analysis(image: np.ndarray) -> np.ndarray:
    """Convert grayscale outputs back to BGR for analyzers expecting 3 channels."""
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return image


def apply_median_filter(image: np.ndarray, ksize: int = 5) -> np.ndarray:
    """Apply a median low-pass filter with cv2.medianBlur."""
    return cv2.medianBlur(image, _ensure_odd_positive(int(ksize), name="ksize"))


def apply_gaussian_filter(
    image: np.ndarray,
    ksize: tuple[int, int] = (5, 5),
    sigma: float = 0,
) -> np.ndarray:
    """Apply a Gaussian low-pass filter with cv2.GaussianBlur."""
    return cv2.GaussianBlur(image, _ensure_odd_kernel(ksize), sigma)


def apply_histogram_equalization_gray(image: np.ndarray) -> np.ndarray:
    """Equalize a BGR image after converting it to grayscale."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.equalizeHist(gray)


def apply_histogram_equalization_color(image: np.ndarray) -> np.ndarray:
    """Equalize only the luminance channel in YCrCb to preserve wound colors."""
    ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
    y, cr, cb = cv2.split(ycrcb)
    y_eq = cv2.equalizeHist(y)
    ycrcb_eq = cv2.merge((y_eq, cr, cb))
    return cv2.cvtColor(ycrcb_eq, cv2.COLOR_YCrCb2BGR)


def apply_clahe_color(
    image: np.ndarray,
    clip_limit: float = 2.0,
    tile_grid_size: tuple[int, int] = (8, 8),
) -> np.ndarray:
    """Apply CLAHE on the LAB luminance channel."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    l_clahe = clahe.apply(l)
    lab_clahe = cv2.merge((l_clahe, a, b))
    return cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)


def apply_median_equalized(image: np.ndarray, ksize: int = 5) -> np.ndarray:
    return apply_histogram_equalization_color(apply_median_filter(image, ksize=ksize))


def apply_gaussian_equalized(
    image: np.ndarray,
    ksize: tuple[int, int] = (5, 5),
    sigma: float = 0,
) -> np.ndarray:
    return apply_histogram_equalization_color(apply_gaussian_filter(image, ksize=ksize, sigma=sigma))


def apply_median_clahe(image: np.ndarray, ksize: int = 5) -> np.ndarray:
    return apply_clahe_color(apply_median_filter(image, ksize=ksize))


def apply_gaussian_clahe(
    image: np.ndarray,
    ksize: tuple[int, int] = (5, 5),
    sigma: float = 0,
) -> np.ndarray:
    return apply_clahe_color(apply_gaussian_filter(image, ksize=ksize, sigma=sigma))


def get_preprocessing_methods() -> "OrderedDict[str, ImageTransform]":
    """Return all experimental variants in the order used by reports."""
    return OrderedDict(
        [
            ("original", lambda image: image.copy()),
            ("median", apply_median_filter),
            ("gaussian", apply_gaussian_filter),
            ("equalized_gray", apply_histogram_equalization_gray),
            ("equalized_color", apply_histogram_equalization_color),
            ("clahe_color", apply_clahe_color),
            ("median_equalized", apply_median_equalized),
            ("gaussian_equalized", apply_gaussian_equalized),
            ("median_clahe", apply_median_clahe),
            ("gaussian_clahe", apply_gaussian_clahe),
        ]
    )


def iter_image_files(input_dir: str | Path) -> list[Path]:
    """Find supported image files recursively, sorted for reproducibility."""
    root = Path(input_dir)
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    )
