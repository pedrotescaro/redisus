import { buildHealAnalyzerRoiSelection } from '../../lib/heal-analyzer-roi';
import type { ClinicalAnalysisAlert, Evaluation, Patient, Roi } from '../../lib/types';
import { analyzeWithHealAnalyzer, type HealAnalyzerResult } from './heal-analyzer-service';
import {
  buildClinicalContextAlerts,
  buildClinicalContextAnalysis,
  buildClinicalContextRecommendations,
  type ClinicalContextAnalysisResult
} from './clinicalContextAnalysisService';
import { defaultPoorImageQuality, evaluateRoiImageQuality, type WoundImageQualityResult } from './imageQualityService';
import { cropImageByRoi, type RoiCropResult } from './roiCropService';
import { classifyTissue, type TissueClassificationResult } from './tissueClassificationService';
import { detectWoundInValidatedRoi, type WoundDetectionResult } from './woundDetectionService';
import { applyServerSegmentation, segmentWoundRoi, type WoundSegmentationResult } from './woundSegmentationService';
import {
  WOUND_ANALYZER_BLOCKED_ROI_MESSAGE,
  WOUND_ANALYZER_UNRELIABLE_CLASSIFICATION_MESSAGE,
  validateWoundInput,
  validateWoundRoi,
  type RoiValidationResult
} from './woundInputValidationService';

export interface WoundAnalysisPipelineInput {
  patient: Patient | null;
  assessment: Evaluation | null;
  image: File | string | null;
  rois: Roi[];
  previousAssessments: Evaluation[];
}

export interface WoundAnalysisPipelineResult {
  canAnalyze: boolean;
  blockedReason?: string;
  imageQuality: WoundImageQualityResult;
  roiValidation: RoiValidationResult;
  woundDetection: WoundDetectionResult;
  segmentation: WoundSegmentationResult;
  tissueClassification: TissueClassificationResult;
  clinicalContext: ClinicalContextAnalysisResult;
  alerts: ClinicalAnalysisAlert[];
  recommendations: string[];
  disclaimer: string;
  selectedRoi?: Roi;
  roiCrop?: RoiCropResult;
  analyzerResult?: HealAnalyzerResult | null;
}

export const HEAL_ANALYZER_PIPELINE_VERSION = 'heal-wound-safe-pipeline-2026-05-07';
export const HEAL_ANALYZER_ASSISTIVE_DISCLAIMER =
  'Esta analise e assistiva e nao substitui avaliacao clinica profissional.';

const SERVER_INFERENCE_ENABLED =
  import.meta.env.VITE_HEAL_ANALYZER_ENABLE_SERVER_INFERENCE !== 'false';

function emptyRoiValidation(reason: string): RoiValidationResult {
  return {
    isValid: false,
    woundLikelihood: 0,
    reason,
    issues: ['pipeline_blocked'],
    areaRatio: 0,
    features: {
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
    }
  };
}

function blockedDetection(reason: string): WoundDetectionResult {
  return {
    hasWound: false,
    confidence: 0,
    reason,
    mode: 'roi_validation_gate',
    modelVersion: 'heal-roi-validation-gate-2026-05'
  };
}

function blockedSegmentation(reason: string): WoundSegmentationResult {
  return {
    method: 'manual_roi_mask',
    limited: true,
    reason
  };
}

function blockedClassification(reason: string): TissueClassificationResult {
  return {
    enabled: false,
    classes: [],
    reason
  };
}

function addAlert(alerts: ClinicalAnalysisAlert[], severity: ClinicalAnalysisAlert['severity'], title: string, message: string) {
  alerts.push({ severity, title, message });
}

async function tryServerInference(crop: RoiCropResult, patientId?: string) {
  if (!SERVER_INFERENCE_ENABLED) return null;

  const roiSelection = buildHealAnalyzerRoiSelection('polygon', crop.cropRoiPoints, crop.width, crop.height);
  return analyzeWithHealAnalyzer(crop.file, {
    patientId,
    roiSelection
  });
}

async function buildRoiCandidates(image: File | string, rois: Roi[]) {
  const candidates: Array<{
    roi: Roi;
    crop: RoiCropResult;
    imageQuality: WoundImageQualityResult;
    roiValidation: RoiValidationResult;
  }> = [];

  for (const roi of rois) {
    const crop = await cropImageByRoi(image, roi);
    const imageQuality = evaluateRoiImageQuality(crop);
    const roiValidation = validateWoundRoi(crop, imageQuality);
    candidates.push({ roi, crop, imageQuality, roiValidation });
  }

  return candidates.sort((left, right) => right.roiValidation.woundLikelihood - left.roiValidation.woundLikelihood);
}

export const woundAnalysisPipeline = {
  async run(input: WoundAnalysisPipelineInput): Promise<WoundAnalysisPipelineResult> {
    const clinicalContext = buildClinicalContextAnalysis(input.patient, input.assessment);
    const inputValidation = validateWoundInput({ image: input.image, rois: input.rois });

    if (!inputValidation.canProceed || !input.image) {
      const reason = inputValidation.reason || WOUND_ANALYZER_BLOCKED_ROI_MESSAGE;
      const imageQuality = defaultPoorImageQuality(!input.image ? 'missing_image' : 'missing_roi');
      const roiValidation = emptyRoiValidation(reason);
      const alerts = buildClinicalContextAlerts({
        assessment: input.assessment,
        clinicalContext,
        imageQuality,
        roiValidation
      });
      addAlert(alerts, 'high', 'Analise visual bloqueada', reason);

      return {
        canAnalyze: false,
        blockedReason: reason,
        imageQuality,
        roiValidation,
        woundDetection: blockedDetection(reason),
        segmentation: blockedSegmentation(reason),
        tissueClassification: blockedClassification(WOUND_ANALYZER_UNRELIABLE_CLASSIFICATION_MESSAGE),
        clinicalContext,
        alerts,
        recommendations: buildClinicalContextRecommendations({
          canAnalyze: false,
          imageQuality,
          hasPatient: Boolean(input.patient),
          hasAssessment: Boolean(input.assessment)
        }),
        disclaimer: HEAL_ANALYZER_ASSISTIVE_DISCLAIMER
      };
    }

    let candidates: Awaited<ReturnType<typeof buildRoiCandidates>> = [];
    try {
      candidates = await buildRoiCandidates(input.image, inputValidation.validRois);
    } catch (error) {
      const reason = error instanceof Error ? error.message : 'Nao foi possivel recortar a ROI para analise.';
      const imageQuality = defaultPoorImageQuality('roi_crop_failed');
      const roiValidation = emptyRoiValidation(reason);
      const alerts = buildClinicalContextAlerts({
        assessment: input.assessment,
        clinicalContext,
        imageQuality,
        roiValidation
      });
      addAlert(alerts, 'high', 'Recorte da ROI indisponivel', reason);

      return {
        canAnalyze: false,
        blockedReason: reason,
        imageQuality,
        roiValidation,
        woundDetection: blockedDetection(reason),
        segmentation: blockedSegmentation(reason),
        tissueClassification: blockedClassification(WOUND_ANALYZER_UNRELIABLE_CLASSIFICATION_MESSAGE),
        clinicalContext,
        alerts,
        recommendations: buildClinicalContextRecommendations({
          canAnalyze: false,
          imageQuality,
          hasPatient: Boolean(input.patient),
          hasAssessment: Boolean(input.assessment)
        }),
        disclaimer: HEAL_ANALYZER_ASSISTIVE_DISCLAIMER
      };
    }

    const selected = candidates[0];
    if (!selected) {
      const reason = WOUND_ANALYZER_BLOCKED_ROI_MESSAGE;
      const imageQuality = defaultPoorImageQuality('missing_valid_roi');
      const roiValidation = emptyRoiValidation(reason);

      return {
        canAnalyze: false,
        blockedReason: reason,
        imageQuality,
        roiValidation,
        woundDetection: blockedDetection(reason),
        segmentation: blockedSegmentation(reason),
        tissueClassification: blockedClassification(WOUND_ANALYZER_UNRELIABLE_CLASSIFICATION_MESSAGE),
        clinicalContext,
        alerts: [{ severity: 'high', title: 'Analise visual bloqueada', message: reason }],
        recommendations: buildClinicalContextRecommendations({
          canAnalyze: false,
          imageQuality,
          hasPatient: Boolean(input.patient),
          hasAssessment: Boolean(input.assessment)
        }),
        disclaimer: HEAL_ANALYZER_ASSISTIVE_DISCLAIMER
      };
    }

    const { roi, crop, imageQuality, roiValidation } = selected;
    const woundDetection = detectWoundInValidatedRoi(roiValidation);
    const alerts = buildClinicalContextAlerts({
      assessment: input.assessment,
      clinicalContext,
      imageQuality,
      roiValidation
    });

    if (!woundDetection.hasWound) {
      const reason = roiValidation.reason || WOUND_ANALYZER_BLOCKED_ROI_MESSAGE;
      addAlert(alerts, 'high', 'Imagem nao adequada para analise de ferida', reason);
      return {
        canAnalyze: false,
        blockedReason: reason,
        imageQuality,
        roiValidation,
        woundDetection,
        segmentation: blockedSegmentation(reason),
        tissueClassification: blockedClassification(WOUND_ANALYZER_UNRELIABLE_CLASSIFICATION_MESSAGE),
        clinicalContext,
        alerts,
        recommendations: buildClinicalContextRecommendations({
          canAnalyze: false,
          imageQuality,
          hasPatient: Boolean(input.patient),
          hasAssessment: Boolean(input.assessment)
        }),
        disclaimer: HEAL_ANALYZER_ASSISTIVE_DISCLAIMER,
        selectedRoi: roi,
        roiCrop: crop
      };
    }

    let segmentation = segmentWoundRoi(crop, woundDetection);

    let analyzerResult: HealAnalyzerResult | null = null;
    if (SERVER_INFERENCE_ENABLED) {
      try {
        analyzerResult = await tryServerInference(crop, input.patient?.id || input.assessment?.patientId);
        if (analyzerResult) segmentation = applyServerSegmentation(segmentation, analyzerResult);
      } catch (error) {
        addAlert(
          alerts,
          'medium',
          'Inferencia visual indisponivel',
          error instanceof Error ? error.message : 'O servico de inferencia visual nao retornou resultado.'
        );
      }
    } else {
      addAlert(
        alerts,
        'low',
        'Classificacao experimental desativada',
        'O sistema esta em modo seguro: sem modelo validado habilitado, nao ha classificacao tecidual automatica.'
      );
    }

    if (segmentation.limited) {
      addAlert(alerts, 'medium', 'Segmentacao limitada', segmentation.reason || 'A segmentacao automatica validada ainda nao esta habilitada.');
    }

    const tissueClassification = classifyTissue({ detection: woundDetection, segmentation, analyzerResult });
    if (!tissueClassification.enabled) {
      addAlert(alerts, 'medium', 'Classificacao tecidual indisponivel', tissueClassification.reason);
    }

    return {
      canAnalyze: true,
      imageQuality,
      roiValidation,
      woundDetection,
      segmentation,
      tissueClassification,
      clinicalContext,
      alerts,
      recommendations: buildClinicalContextRecommendations({
        canAnalyze: true,
        imageQuality,
        hasPatient: Boolean(input.patient),
        hasAssessment: Boolean(input.assessment)
      }),
      disclaimer: HEAL_ANALYZER_ASSISTIVE_DISCLAIMER,
      selectedRoi: roi,
      roiCrop: crop,
      analyzerResult
    };
  }
};
