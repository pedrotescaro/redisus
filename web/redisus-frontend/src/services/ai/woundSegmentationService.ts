import type { RoiCropResult } from './roiCropService';
import type { WoundDetectionResult } from './woundDetectionService';

export interface WoundSegmentationResult {
  maskUrl?: string;
  areaPixels?: number;
  overlayUrl?: string;
  confidence?: number;
  method: 'manual_roi_mask' | 'trained_segmentation_model';
  limited: boolean;
  reason?: string;
}

function buildMaskCanvas(crop: RoiCropResult) {
  const canvas = document.createElement('canvas');
  canvas.width = crop.width;
  canvas.height = crop.height;
  const context = canvas.getContext('2d');
  if (!context) return null;
  const imageData = context.createImageData(crop.width, crop.height);

  for (let index = 0; index < crop.mask.length; index += 1) {
    const offset = index * 4;
    const value = crop.mask[index];
    imageData.data[offset] = value;
    imageData.data[offset + 1] = value;
    imageData.data[offset + 2] = value;
    imageData.data[offset + 3] = 255;
  }

  context.putImageData(imageData, 0, 0);
  return canvas;
}

function buildOverlayCanvas(crop: RoiCropResult) {
  const canvas = document.createElement('canvas');
  canvas.width = crop.width;
  canvas.height = crop.height;
  const context = canvas.getContext('2d');
  if (!context) return null;
  context.drawImage(crop.canvas, 0, 0);

  const colorCanvas = document.createElement('canvas');
  colorCanvas.width = crop.width;
  colorCanvas.height = crop.height;
  const colorContext = colorCanvas.getContext('2d');
  if (!colorContext) return canvas;
  const overlay = colorContext.createImageData(crop.width, crop.height);
  for (let index = 0; index < crop.mask.length; index += 1) {
    if (!crop.mask[index]) continue;
    const offset = index * 4;
    overlay.data[offset] = 20;
    overlay.data[offset + 1] = 184;
    overlay.data[offset + 2] = 166;
    overlay.data[offset + 3] = 78;
  }
  colorContext.putImageData(overlay, 0, 0);
  context.drawImage(colorCanvas, 0, 0);
  context.lineWidth = Math.max(2, Math.round(Math.max(crop.width, crop.height) * 0.006));
  context.strokeStyle = '#0f766e';
  context.beginPath();
  crop.cropRoiPoints.forEach((point, index) => {
    const x = point.x * crop.width;
    const y = point.y * crop.height;
    if (index === 0) context.moveTo(x, y);
    else context.lineTo(x, y);
  });
  context.closePath();
  context.stroke();
  return canvas;
}

export function segmentWoundRoi(crop: RoiCropResult, detection: WoundDetectionResult): WoundSegmentationResult {
  if (!detection.hasWound) {
    return {
      method: 'manual_roi_mask',
      limited: true,
      reason: 'Segmentacao bloqueada porque a ROI nao passou na validacao de ferida.'
    };
  }

  const maskCanvas = buildMaskCanvas(crop);
  const overlayCanvas = buildOverlayCanvas(crop);

  return {
    maskUrl: maskCanvas?.toDataURL('image/png'),
    overlayUrl: overlayCanvas?.toDataURL('image/png'),
    areaPixels: crop.areaPixels,
    confidence: Math.min(0.69, detection.confidence),
    method: 'manual_roi_mask',
    limited: true,
    reason: 'Sem modelo de segmentacao de ferida treinado e validado nesta instalacao; exibindo mascara manual da ROI como referencia.'
  };
}
