import type { RoiValidationResult } from './woundInputValidationService';
import { WOUND_ANALYSIS_SAFETY_THRESHOLDS } from './woundInputValidationService';

export interface WoundDetectionResult {
  hasWound: boolean;
  confidence: number;
  reason: string;
  mode: 'roi_validation_gate' | 'trained_model';
  modelVersion: string;
}

export function detectWoundInValidatedRoi(roiValidation: RoiValidationResult): WoundDetectionResult {
  const hasWound = roiValidation.isValid && roiValidation.woundLikelihood >= WOUND_ANALYSIS_SAFETY_THRESHOLDS.minWoundLikelihood;

  return {
    hasWound,
    confidence: roiValidation.woundLikelihood,
    reason: hasWound
      ? 'Gate visual da ROI aprovado. A etapa ainda nao equivale a um modelo clinico validado.'
      : roiValidation.reason,
    mode: 'roi_validation_gate',
    modelVersion: 'heal-roi-validation-gate-2026-05'
  };
}
