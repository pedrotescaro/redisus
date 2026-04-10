from __future__ import annotations

import numpy as np

from src.diagnosis.two_stage_tissue_pipeline import TwoStageTissuePipeline


class DummyWoundSegmenter:
    def segment(self, image: np.ndarray):
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        mask[20:80, 25:85] = 255
        return {"wound_mask": mask}


class DummyTissueSegmenter:
    def segment(self, image: np.ndarray):
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        mask[:, : image.shape[1] // 2] = 1  # granulacao
        mask[:, image.shape[1] // 2 :] = 3  # necrose
        return {"mask": mask}


def test_two_stage_pipeline_crops_then_projects_tissue_mask_back():
    image = np.zeros((100, 120, 3), dtype=np.uint8)
    pipeline = TwoStageTissuePipeline(
        DummyWoundSegmenter(),
        DummyTissueSegmenter(),
        crop_margin_ratio=0.0,
    )

    result = pipeline.analyze(image)

    assert result.wound_area_pixels == 60 * 60
    assert result.crop_bbox == (21, 16, 89, 84)
    assert result.tissue_mask.shape == image.shape[:2]
    assert np.all(result.tissue_mask[result.wound_mask == 0] == 0)
    assert result.tissue_percentages["Granulação"] > 40.0
    assert result.tissue_percentages["Necrose"] > 40.0
