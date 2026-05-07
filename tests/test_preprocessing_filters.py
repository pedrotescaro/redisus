import cv2
import numpy as np
import pytest

from src.processing.preprocessing_filters import (
    apply_clahe_color,
    apply_gaussian_clahe,
    apply_gaussian_equalized,
    apply_gaussian_filter,
    apply_histogram_equalization_color,
    apply_histogram_equalization_gray,
    apply_median_clahe,
    apply_median_equalized,
    apply_median_filter,
    ensure_bgr_for_analysis,
    get_preprocessing_methods,
)


def synthetic_bgr_image() -> np.ndarray:
    image = np.zeros((80, 90, 3), dtype=np.uint8)
    image[:, :, 0] = 40
    image[:, :, 1] = np.linspace(20, 220, 90, dtype=np.uint8)
    image[:, :, 2] = 180
    cv2.circle(image, (45, 40), 18, (30, 80, 210), -1)
    return image


def test_preprocessing_methods_keep_expected_shapes():
    image = synthetic_bgr_image()

    assert apply_median_filter(image).shape == image.shape
    assert apply_gaussian_filter(image).shape == image.shape
    assert apply_histogram_equalization_gray(image).shape == image.shape[:2]
    assert apply_histogram_equalization_color(image).shape == image.shape
    assert apply_clahe_color(image).shape == image.shape
    assert apply_median_equalized(image).shape == image.shape
    assert apply_gaussian_equalized(image).shape == image.shape
    assert apply_median_clahe(image).shape == image.shape
    assert apply_gaussian_clahe(image).shape == image.shape


def test_gray_equalization_can_be_converted_back_to_bgr_for_analysis():
    image = synthetic_bgr_image()
    gray = apply_histogram_equalization_gray(image)
    bgr = ensure_bgr_for_analysis(gray)

    assert bgr.shape == image.shape
    assert bgr.ndim == 3


def test_registered_methods_include_expected_experimental_variants():
    methods = get_preprocessing_methods()

    assert list(methods) == [
        "original",
        "median",
        "gaussian",
        "equalized_gray",
        "equalized_color",
        "clahe_color",
        "median_equalized",
        "gaussian_equalized",
        "median_clahe",
        "gaussian_clahe",
    ]


def test_even_kernel_sizes_are_rejected():
    image = synthetic_bgr_image()

    with pytest.raises(ValueError):
        apply_median_filter(image, ksize=4)

    with pytest.raises(ValueError):
        apply_gaussian_filter(image, ksize=(4, 5))
