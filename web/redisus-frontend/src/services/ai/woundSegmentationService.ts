import type { RoiCropResult } from './roiCropService';
import type { HealAnalyzerResult } from './heal-analyzer-service';
import type { WoundDetectionResult } from './woundDetectionService';

export interface WoundSegmentationResult {
  maskUrl?: string;
  areaPixels?: number;
  overlayUrl?: string;
  confidence?: number;
  method: 'manual_roi_mask' | 'clinical_backend' | 'heuristic_preview';
  limited: boolean;
  reason?: string;
  coveragePercent?: number;
  unclassifiedPercent?: number;
  computedPercentages?: {
    necrosis: number;
    slough_fibrin: number;
    granulation: number;
    epithelial: number;
  };
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

function buildTissueSegmentationCanvas(crop: RoiCropResult) {
  const canvas = document.createElement('canvas');
  canvas.width = crop.width;
  canvas.height = crop.height;
  const context = canvas.getContext('2d');
  if (!context) return null;

  // Draw the original image first
  context.drawImage(crop.canvas, 0, 0);

  // Get image pixels
  const imgData = context.getImageData(0, 0, crop.width, crop.height);
  const data = imgData.data;

  // Create an overlay image data
  const overlayCanvas = document.createElement('canvas');
  overlayCanvas.width = crop.width;
  overlayCanvas.height = crop.height;
  const overlayCtx = overlayCanvas.getContext('2d');
  if (!overlayCtx) return { canvas, percentages: { necrosis: 0, slough_fibrin: 0, granulation: 0, epithelial: 0 } };
  const overlayData = overlayCtx.createImageData(crop.width, crop.height);

  let necrosisCount = 0;
  let sloughCount = 0;
  let granulationCount = 0;
  let epithelialCount = 0;
  let totalWoundPixels = 0;

  for (let y = 0; y < crop.height; y++) {
    for (let x = 0; x < crop.width; x++) {
      const idx = y * crop.width + x;
      const maskValue = crop.mask[idx];
      if (maskValue === 0) continue; // outside ROI

      const offset = idx * 4;
      const r = data[offset];
      const g = data[offset + 1];
      const b = data[offset + 2];

      totalWoundPixels++;

      // Tissue classification heuristics based on RGB and brightness
      const brightness = 0.299 * r + 0.587 * g + 0.114 * b;

      // 1. Necrosis (Very dark / black / dark brown)
      if (brightness < 60) {
        necrosisCount++;
        overlayData.data[offset] = 24;      // dark grey
        overlayData.data[offset + 1] = 24;
        overlayData.data[offset + 2] = 27;
        overlayData.data[offset + 3] = 160;
      }
      // 2. Slough (Yellowish / Pale Cream / Fibrin)
      else if (r > 130 && g > 120 && b < 160) {
        sloughCount++;
        overlayData.data[offset] = 234;     // yellow
        overlayData.data[offset + 1] = 179;
        overlayData.data[offset + 2] = 8;
        overlayData.data[offset + 3] = 160;
      }
      // 3. Granulation (Vibrant red / pink)
      else if (r > g * 1.15 && r > b * 1.15) {
        granulationCount++;
        overlayData.data[offset] = 220;     // red
        overlayData.data[offset + 1] = 38;
        overlayData.data[offset + 2] = 38;
        overlayData.data[offset + 3] = 160;
      }
      // 4. Epithelialization (Light pink / purple / green overlay for visual distinction)
      else {
        epithelialCount++;
        overlayData.data[offset] = 16;      // emerald green
        overlayData.data[offset + 1] = 185;
        overlayData.data[offset + 2] = 129;
        overlayData.data[offset + 3] = 160;
      }
    }
  }

  overlayCtx.putImageData(overlayData, 0, 0);
  context.drawImage(overlayCanvas, 0, 0);

  // Draw ROI borders
  context.lineWidth = Math.max(2, Math.round(Math.max(crop.width, crop.height) * 0.006));
  context.strokeStyle = '#38bdf8'; // light sky blue outline
  context.beginPath();
  crop.cropRoiPoints.forEach((point, index) => {
    const x = point.x * crop.width;
    const y = point.y * crop.height;
    if (index === 0) context.moveTo(x, y);
    else context.lineTo(x, y);
  });
  context.closePath();
  context.stroke();

  // Calculate percentages
  const pctNecrosis = totalWoundPixels > 0 ? (necrosisCount / totalWoundPixels) * 100 : 0;
  const pctSlough = totalWoundPixels > 0 ? (sloughCount / totalWoundPixels) * 100 : 0;
  const pctGranulation = totalWoundPixels > 0 ? (granulationCount / totalWoundPixels) * 100 : 0;
  const pctEpithelial = totalWoundPixels > 0 ? (epithelialCount / totalWoundPixels) * 100 : 0;

  return {
    canvas,
    percentages: {
      necrosis: pctNecrosis,
      slough_fibrin: pctSlough,
      granulation: pctGranulation,
      epithelial: pctEpithelial,
    }
  };
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
  const tissueSegmentation = buildTissueSegmentationCanvas(crop);

  const overlayCanvas = tissueSegmentation ? tissueSegmentation.canvas : crop.canvas;
  const percentages = tissueSegmentation
    ? tissueSegmentation.percentages
    : { necrosis: 0, slough_fibrin: 0, granulation: 0, epithelial: 0 };

  return {
    maskUrl: maskCanvas?.toDataURL('image/png'),
    overlayUrl: overlayCanvas.toDataURL('image/png'),
    areaPixels: crop.areaPixels,
    confidence: Math.min(0.45, detection.confidence),
    method: 'heuristic_preview',
    limited: true,
    reason: 'Previa visual heuristica local. A leitura clinica de tecidos depende do mapa retornado pela API.',
    computedPercentages: percentages
  };
}

function normalizeTissueKey(value: string): keyof NonNullable<WoundSegmentationResult['computedPercentages']> | null {
  const normalized = value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();

  if (normalized.includes('granulation') || normalized.includes('granulacao')) return 'granulation';
  if (normalized.includes('slough') || normalized.includes('esfacelo') || normalized.includes('fibrin')) return 'slough_fibrin';
  if (normalized.includes('necros') || normalized.includes('eschar') || normalized.includes('escara')) return 'necrosis';
  if (normalized.includes('epithel') || normalized.includes('epitel')) return 'epithelial';
  return null;
}

function serverTissuePercentages(result: HealAnalyzerResult) {
  const percentages = {
    necrosis: 0,
    slough_fibrin: 0,
    granulation: 0,
    epithelial: 0
  };

  for (const tissue of result.tissues || []) {
    const key = normalizeTissueKey(`${tissue.name} ${tissue.name_en}`);
    if (key) percentages[key] += Math.max(0, Number(tissue.percentage || 0));
  }

  return percentages;
}

export function applyServerSegmentation(
  preview: WoundSegmentationResult,
  result: HealAnalyzerResult
): WoundSegmentationResult {
  const segmentationUrl = result.visuals?.segmentation?.data_url || undefined;
  const combinedUrl = result.visuals?.combined?.data_url || segmentationUrl;
  const coverage = Math.max(0, Math.min(100, Number(result.tissue_analysis_trace?.coverage_pct ?? 0)));
  const unclassified = Math.max(
    0,
    Math.min(100, Number(result.tissue_analysis_trace?.unclassified_pct ?? (coverage > 0 ? 100 - coverage : 0)))
  );
  const inferenceConfidence = Number(result.inference?.confidence || 0);
  const hasClinicalVisual = Boolean(combinedUrl || segmentationUrl);
  const coverageSummary = coverage > 0
    ? ` Cobertura classificada: ${coverage.toFixed(1)}%; area incerta: ${unclassified.toFixed(1)}%.`
    : '';

  return {
    ...preview,
    maskUrl: segmentationUrl || preview.maskUrl,
    overlayUrl: combinedUrl || preview.overlayUrl,
    areaPixels: Number(result.wound_area_px || preview.areaPixels || 0),
    confidence: inferenceConfidence > 0 ? Math.min(1, inferenceConfidence) : undefined,
    method: hasClinicalVisual ? 'clinical_backend' : 'heuristic_preview',
    limited: !result.is_valid_wound || !hasClinicalVisual || unclassified > 15,
    reason: hasClinicalVisual
      ? `Mapa clinico produzido pela API com HSV/LAB, textura e zonas espaciais.${coverageSummary}`
      : preview.reason,
    coveragePercent: coverage || undefined,
    unclassifiedPercent: coverage > 0 ? unclassified : undefined,
    computedPercentages: serverTissuePercentages(result)
  };
}
