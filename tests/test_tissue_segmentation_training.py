from __future__ import annotations

import numpy as np

from src.core.config import TissueType, get_tissue_color_map
from src.training.tissue_segmentation_training import decode_tissue_mask


def test_decode_tissue_mask_accepts_indexed_grayscale():
    mask = np.array(
        [
            [0, 1, 2],
            [3, 4, 0],
        ],
        dtype=np.uint8,
    )

    decoded = decode_tissue_mask(mask)

    assert np.array_equal(decoded, mask)


def test_decode_tissue_mask_maps_rgb_colors_to_class_indices():
    color_map = get_tissue_color_map()
    rgb_mask = np.array(
        [
            [color_map[TissueType.GRANULATION.value], color_map[TissueType.SLOUGH.value]],
            [color_map[TissueType.NECROSIS.value], color_map[TissueType.PERIWOUND.value]],
        ],
        dtype=np.uint8,
    )
    bgr_mask = rgb_mask[..., ::-1]

    decoded = decode_tissue_mask(bgr_mask)

    assert decoded[0, 0] == TissueType.GRANULATION.value
    assert decoded[0, 1] == TissueType.SLOUGH.value
    assert decoded[1, 0] == TissueType.NECROSIS.value
    assert decoded[1, 1] == TissueType.PERIWOUND.value
