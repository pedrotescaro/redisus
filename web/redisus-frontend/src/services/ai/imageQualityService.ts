import type { RoiCropResult } from './roiCropService';

export interface WoundImageQualityResult {
  status: 'good' | 'regular' | 'poor';
  score: number;
  issues: string[];
  metrics: {
    width: number;
    height: number;
    brightness: number;
    contrast: number;
    sharpness: number;
  };
  preprocessing: string[];
}

function luminanceAt(data: Uint8ClampedArray, offset: number) {
  return 0.299 * data[offset] + 0.587 * data[offset + 1] + 0.114 * data[offset + 2];
}

export function evaluateImageQualityFromImageData(
  imageData: ImageData,
  options: {
    mask?: Uint8ClampedArray;
    preprocessing?: string[];
  } = {}
): WoundImageQualityResult {
  const { width, height, data } = imageData;
  const luminanceValues: number[] = [];
  let gradientSum = 0;
  let gradientCount = 0;

  for (let y = 0; y < height; y += 2) {
    for (let x = 0; x < width; x += 2) {
      const pixelIndex = y * width + x;
      if (options.mask && !options.mask[pixelIndex]) continue;

      const offset = pixelIndex * 4;
      const luminance = luminanceAt(data, offset);
      luminanceValues.push(luminance);

      if (x + 2 < width) {
        const rightIndex = y * width + x + 2;
        if (!options.mask || options.mask[rightIndex]) {
          gradientSum += Math.abs(luminance - luminanceAt(data, rightIndex * 4));
          gradientCount += 1;
        }
      }
      if (y + 2 < height) {
        const bottomIndex = (y + 2) * width + x;
        if (!options.mask || options.mask[bottomIndex]) {
          gradientSum += Math.abs(luminance - luminanceAt(data, bottomIndex * 4));
          gradientCount += 1;
        }
      }
    }
  }

  const sampleCount = Math.max(luminanceValues.length, 1);
  const brightness = luminanceValues.reduce((sum, value) => sum + value, 0) / sampleCount;
  const variance = luminanceValues.reduce((sum, value) => sum + (value - brightness) ** 2, 0) / sampleCount;
  const contrast = Math.sqrt(variance);
  const sharpness = gradientSum / Math.max(gradientCount, 1);
  const issues: string[] = [];

  if (width < 96 || height < 96 || sampleCount < 2000) issues.push('roi_low_resolution');
  if (brightness < 45) issues.push('low_light');
  if (brightness > 228) issues.push('overexposure');
  if (contrast < 18) issues.push('low_contrast');
  if (sharpness < 5.5) issues.push('possible_blur');

  const score = Math.max(
    0,
    Math.min(
      100,
      100 -
        issues.length * 16 -
        (contrast < 24 ? 8 : 0) -
        (sharpness < 8 ? 8 : 0)
    )
  );
  const status = score >= 78 ? 'good' : score >= 52 ? 'regular' : 'poor';

  return {
    status,
    score: Math.round(score),
    issues,
    metrics: {
      width,
      height,
      brightness: Math.round(brightness),
      contrast: Math.round(contrast),
      sharpness: Math.round(sharpness)
    },
    preprocessing: options.preprocessing || ['roi_crop', 'roi_mask']
  };
}

export function evaluateRoiImageQuality(crop: RoiCropResult): WoundImageQualityResult {
  return evaluateImageQualityFromImageData(crop.imageData, {
    mask: crop.mask,
    preprocessing: ['roi_crop', 'manual_roi_mask']
  });
}

export function defaultPoorImageQuality(issue = 'missing_image'): WoundImageQualityResult {
  return {
    status: 'poor',
    score: 0,
    issues: [issue],
    metrics: {
      width: 0,
      height: 0,
      brightness: 0,
      contrast: 0,
      sharpness: 0
    },
    preprocessing: []
  };
}
