import { describe, expect, it } from 'vitest';

import type { WoundImageQualityResult } from '../../services/ai/imageQualityService';
import type { RoiCropResult } from '../../services/ai/roiCropService';
import { validateWoundRoi } from '../../services/ai/woundInputValidationService';

function quality(overrides: Partial<WoundImageQualityResult> = {}): WoundImageQualityResult {
  return {
    status: 'good',
    score: 86,
    issues: [],
    metrics: {
      width: 100,
      height: 100,
      brightness: 120,
      contrast: 42,
      sharpness: 13
    },
    preprocessing: ['roi_crop'],
    ...overrides
  };
}

function cropFromPixels(pixels: Array<[number, number, number]>): RoiCropResult {
  const width = 100;
  const height = 100;
  const data = new Uint8ClampedArray(width * height * 4);
  for (let index = 0; index < width * height; index += 1) {
    const [red, green, blue] = pixels[index % pixels.length];
    const offset = index * 4;
    data[offset] = red;
    data[offset + 1] = green;
    data[offset + 2] = blue;
    data[offset + 3] = 255;
  }

  const canvas = document.createElement('canvas');
  return {
    roi: null,
    roiPoints: [],
    cropRoiPoints: [],
    boundingBox: { x: 0, y: 0, width: 1, height: 1 },
    areaPixels: width * height,
    areaRatio: 0.08,
    width,
    height,
    originalWidth: width,
    originalHeight: height,
    canvas,
    maskedCanvas: canvas,
    imageData: { data, width, height, colorSpace: 'srgb' } as ImageData,
    mask: new Uint8ClampedArray(width * height).fill(255),
    dataUrl: '',
    maskedDataUrl: '',
    file: {} as File
  };
}

describe('wound ROI validation gate', () => {
  it('blocks clothing/background-like ROIs', () => {
    const result = validateWoundRoi(cropFromPixels([[20, 90, 210]]), quality());
    expect(result.isValid).toBe(false);
    expect(result.issues).toContain('probable_clothing_or_object');
  });

  it('allows a varied wound-like ROI without producing tissue labels', () => {
    const result = validateWoundRoi(
      cropFromPixels([
        [175, 35, 35],
        [165, 118, 38],
        [42, 28, 24],
        [210, 118, 118]
      ]),
      quality()
    );
    expect(result.isValid).toBe(true);
    expect(result.woundLikelihood).toBeGreaterThanOrEqual(0.6);
  });
});
