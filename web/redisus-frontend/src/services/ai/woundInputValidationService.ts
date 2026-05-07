import type { Roi } from '../../lib/types';
import type { WoundImageQualityResult } from './imageQualityService';
import type { RoiCropResult } from './roiCropService';

export const WOUND_ANALYZER_BLOCKED_ROI_MESSAGE =
  'A ROI selecionada nao apresenta caracteristicas visuais suficientes de ferida para analise assistiva. Revise a marcacao ou selecione uma imagem clinica adequada.';

export const WOUND_ANALYZER_UNRELIABLE_CLASSIFICATION_MESSAGE =
  'Nao foi possivel realizar uma classificacao confiavel da ferida. A imagem ou ROI nao contem evidencia visual suficiente de ferida cronica.';

export const WOUND_ANALYSIS_SAFETY_THRESHOLDS = {
  minWoundLikelihood: 0.6,
  minRoiAreaRatio: 0.0015,
  maxRoiAreaRatio: 0.38,
  maxVeryLargeRoiAreaRatio: 0.52,
  minSegmentationConfidence: 0.7
} as const;

export interface WoundVisualFeatures {
  sampledPixels: number;
  redPinkRatio: number;
  yellowBrownRatio: number;
  darkTissueRatio: number;
  paleTissueRatio: number;
  healthySkinLikeRatio: number;
  blueGreenBackgroundRatio: number;
  neutralBackgroundRatio: number;
  saturatedObjectRatio: number;
  woundColorRatio: number;
  colorDiversity: number;
  meanSaturation: number;
  textureScore: number;
  localContrast: number;
}

export interface RoiValidationResult {
  isValid: boolean;
  woundLikelihood: number;
  reason: string;
  issues: string[];
  roiId?: string;
  areaRatio: number;
  features: WoundVisualFeatures;
}

export interface WoundInputValidationResult {
  canProceed: boolean;
  reason?: string;
  validRois: Roi[];
}

function clamp01(value: number) {
  return Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0));
}

function rgbToHsv(red: number, green: number, blue: number) {
  const r = red / 255;
  const g = green / 255;
  const b = blue / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;
  let hue = 0;

  if (delta > 0) {
    if (max === r) hue = 60 * (((g - b) / delta) % 6);
    else if (max === g) hue = 60 * ((b - r) / delta + 2);
    else hue = 60 * ((r - g) / delta + 4);
  }

  if (hue < 0) hue += 360;
  return {
    h: hue,
    s: max === 0 ? 0 : delta / max,
    v: max
  };
}

function emptyFeatures(): WoundVisualFeatures {
  return {
    sampledPixels: 0,
    redPinkRatio: 0,
    yellowBrownRatio: 0,
    darkTissueRatio: 0,
    paleTissueRatio: 0,
    healthySkinLikeRatio: 0,
    blueGreenBackgroundRatio: 0,
    neutralBackgroundRatio: 0,
    saturatedObjectRatio: 0,
    woundColorRatio: 0,
    colorDiversity: 0,
    meanSaturation: 0,
    textureScore: 0,
    localContrast: 0
  };
}

function calculateTextureScore(quality: WoundImageQualityResult) {
  const contrastPart = clamp01((quality.metrics.contrast - 14) / 42);
  const sharpnessPart = clamp01((quality.metrics.sharpness - 4) / 16);
  return clamp01(contrastPart * 0.58 + sharpnessPart * 0.42);
}

export function validateWoundInput(options: { image: File | string | null; rois: Roi[] }): WoundInputValidationResult {
  if (!options.image) {
    return { canProceed: false, reason: 'Selecione uma imagem clinica antes de iniciar a analise.', validRois: [] };
  }

  const validRois = options.rois.filter(roi => roi.points.length >= 3);
  if (!validRois.length) {
    return {
      canProceed: false,
      reason: 'Crie ou carregue uma ROI manual antes da analise visual. O HEAL Analyzer nao classifica imagem inteira como ferida.',
      validRois: []
    };
  }

  return { canProceed: true, validRois };
}

export function extractWoundVisualFeatures(crop: RoiCropResult, quality: WoundImageQualityResult): WoundVisualFeatures {
  const { width, height, data } = crop.imageData;
  const counts = {
    redPink: 0,
    yellowBrown: 0,
    darkTissue: 0,
    paleTissue: 0,
    healthySkinLike: 0,
    blueGreenBackground: 0,
    neutralBackground: 0,
    saturatedObject: 0
  };
  let sampledPixels = 0;
  let saturationSum = 0;

  for (let y = 0; y < height; y += 2) {
    for (let x = 0; x < width; x += 2) {
      const pixelIndex = y * width + x;
      if (!crop.mask[pixelIndex]) continue;

      const offset = pixelIndex * 4;
      const red = data[offset];
      const green = data[offset + 1];
      const blue = data[offset + 2];
      const hsv = rgbToHsv(red, green, blue);
      sampledPixels += 1;
      saturationSum += hsv.s;

      const redPink = (hsv.h <= 24 || hsv.h >= 340) && hsv.s >= 0.18 && hsv.v >= 0.18;
      const yellowBrown = hsv.h >= 22 && hsv.h <= 62 && hsv.s >= 0.16 && hsv.v >= 0.22;
      const darkTissue = hsv.v <= 0.26 && hsv.s >= 0.12;
      const paleTissue = hsv.v >= 0.68 && hsv.s <= 0.23 && red >= green && green >= blue;
      const healthySkinLike =
        hsv.h >= 4 &&
        hsv.h <= 48 &&
        hsv.s >= 0.10 &&
        hsv.s <= 0.62 &&
        hsv.v >= 0.36 &&
        red >= blue &&
        green >= blue * 0.85;
      const blueGreenBackground = hsv.h >= 78 && hsv.h <= 205 && hsv.s >= 0.22;
      const neutralBackground = hsv.s <= 0.10 || (Math.abs(red - green) < 12 && Math.abs(green - blue) < 12);
      const saturatedObject = hsv.s >= 0.58 && hsv.v >= 0.25 && !redPink && !yellowBrown;

      if (redPink) counts.redPink += 1;
      if (yellowBrown) counts.yellowBrown += 1;
      if (darkTissue) counts.darkTissue += 1;
      if (paleTissue) counts.paleTissue += 1;
      if (healthySkinLike) counts.healthySkinLike += 1;
      if (blueGreenBackground) counts.blueGreenBackground += 1;
      if (neutralBackground) counts.neutralBackground += 1;
      if (saturatedObject) counts.saturatedObject += 1;
    }
  }

  if (!sampledPixels) return emptyFeatures();

  const redPinkRatio = counts.redPink / sampledPixels;
  const yellowBrownRatio = counts.yellowBrown / sampledPixels;
  const darkTissueRatio = counts.darkTissue / sampledPixels;
  const paleTissueRatio = counts.paleTissue / sampledPixels;
  const woundColorRatio = clamp01(redPinkRatio + yellowBrownRatio + darkTissueRatio + paleTissueRatio * 0.45);
  const colorDiversity = [redPinkRatio, yellowBrownRatio, darkTissueRatio, paleTissueRatio].filter(value => value >= 0.035).length / 4;

  return {
    sampledPixels,
    redPinkRatio,
    yellowBrownRatio,
    darkTissueRatio,
    paleTissueRatio,
    healthySkinLikeRatio: counts.healthySkinLike / sampledPixels,
    blueGreenBackgroundRatio: counts.blueGreenBackground / sampledPixels,
    neutralBackgroundRatio: counts.neutralBackground / sampledPixels,
    saturatedObjectRatio: counts.saturatedObject / sampledPixels,
    woundColorRatio,
    colorDiversity,
    meanSaturation: saturationSum / sampledPixels,
    textureScore: calculateTextureScore(quality),
    localContrast: quality.metrics.contrast / 100
  };
}

export function validateWoundRoi(crop: RoiCropResult, quality: WoundImageQualityResult): RoiValidationResult {
  const issues: string[] = [];
  const features = extractWoundVisualFeatures(crop, quality);
  const areaRatio = crop.areaRatio;

  if (areaRatio < WOUND_ANALYSIS_SAFETY_THRESHOLDS.minRoiAreaRatio) issues.push('roi_too_small');
  if (areaRatio > WOUND_ANALYSIS_SAFETY_THRESHOLDS.maxRoiAreaRatio) issues.push('roi_too_large');
  if (features.sampledPixels < 600) issues.push('roi_insufficient_pixels');
  if (features.woundColorRatio < 0.08) issues.push('insufficient_wound_color');
  if (features.textureScore < 0.18) issues.push('low_biological_texture');
  if (features.healthySkinLikeRatio > 0.74 && features.woundColorRatio < 0.24) issues.push('mostly_intact_skin');
  if (features.blueGreenBackgroundRatio > 0.32 || features.saturatedObjectRatio > 0.48) issues.push('probable_clothing_or_object');
  if (features.neutralBackgroundRatio > 0.76 && features.woundColorRatio < 0.16) issues.push('probable_background_or_gauze');

  const areaScore =
    areaRatio < WOUND_ANALYSIS_SAFETY_THRESHOLDS.minRoiAreaRatio
      ? 0
      : areaRatio > WOUND_ANALYSIS_SAFETY_THRESHOLDS.maxRoiAreaRatio
        ? 0.18
        : areaRatio > 0.24
          ? 0.52
          : 1;
  const colorScore = clamp01(features.woundColorRatio / 0.28);
  const diversityScore = clamp01(features.colorDiversity);
  const textureScore = features.textureScore;
  let woundLikelihood = 0.12 + colorScore * 0.38 + textureScore * 0.26 + areaScore * 0.14 + diversityScore * 0.1;

  if (features.healthySkinLikeRatio > 0.74 && features.woundColorRatio < 0.24) woundLikelihood -= 0.36;
  if (features.blueGreenBackgroundRatio > 0.28) woundLikelihood -= 0.3;
  if (features.saturatedObjectRatio > 0.48) woundLikelihood -= 0.24;
  if (features.neutralBackgroundRatio > 0.76 && features.woundColorRatio < 0.16) woundLikelihood -= 0.28;
  if (features.woundColorRatio < 0.08) woundLikelihood -= 0.28;
  if (areaRatio > WOUND_ANALYSIS_SAFETY_THRESHOLDS.maxRoiAreaRatio) woundLikelihood -= 0.28;
  if (areaRatio > WOUND_ANALYSIS_SAFETY_THRESHOLDS.maxVeryLargeRoiAreaRatio) woundLikelihood = Math.min(woundLikelihood, 0.24);
  if (quality.status === 'poor') woundLikelihood -= 0.06;
  woundLikelihood = clamp01(woundLikelihood);

  const isValid = woundLikelihood >= WOUND_ANALYSIS_SAFETY_THRESHOLDS.minWoundLikelihood && !issues.includes('roi_too_small') && !issues.includes('roi_too_large');
  let reason = 'A ROI apresenta variacao visual compativel com area de ferida, mas ainda requer validacao profissional.';

  if (!isValid) {
    if (issues.includes('roi_too_small')) reason = 'A ROI marcada e pequena demais para analise visual confiavel.';
    else if (issues.includes('roi_too_large')) reason = 'Marque somente a area da ferida. Evite incluir rosto, roupa, fundo, maos, instrumentos ou grandes areas de pele saudavel.';
    else if (issues.includes('probable_clothing_or_object')) reason = 'A ROI contem padroes de cor mais compativeis com roupa, objeto ou fundo do que com leito de ferida.';
    else if (issues.includes('mostly_intact_skin')) reason = 'A ROI parece conter majoritariamente pele integra, sem evidencia visual suficiente de ferida.';
    else if (issues.includes('probable_background_or_gauze')) reason = 'A ROI parece conter fundo, gaze ou area neutra demais para analise tecidual.';
    else reason = WOUND_ANALYZER_BLOCKED_ROI_MESSAGE;
  }

  return {
    isValid,
    woundLikelihood: Number(woundLikelihood.toFixed(3)),
    reason,
    issues,
    roiId: crop.roi?.id,
    areaRatio,
    features
  };
}
