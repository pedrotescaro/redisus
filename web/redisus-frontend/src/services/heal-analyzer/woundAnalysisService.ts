import { ensureClinicalRois } from './roiProcessingService';
import { buildWoundEvolution } from './woundEvolutionService';
import type { ClinicalAnalysisResult, Evaluation, Patient, Roi } from '../../lib/types';
import {
  HEAL_ANALYZER_ASSISTIVE_DISCLAIMER,
  HEAL_ANALYZER_PIPELINE_VERSION,
  woundAnalysisPipeline,
  type WoundAnalysisPipelineResult
} from '../ai/woundAnalysisPipeline';

export const HEAL_ANALYZER_ANALYSIS_VERSION = HEAL_ANALYZER_PIPELINE_VERSION;
export const HEAL_ANALYZER_DISCLAIMER =
  `${HEAL_ANALYZER_ASSISTIVE_DISCLAIMER} Baseada na imagem, ROI e dados disponiveis; pode ser limitada pela qualidade da imagem e pela marcacao da ROI.`;

interface BuildClinicalAnalysisOptions {
  mode: ClinicalAnalysisResult['mode'];
  patient: Patient | null;
  assessment: Evaluation | null;
  history: Evaluation[];
  image: File | string | null;
  imageId?: string;
  rois: Roi[];
  createdBy?: string;
}

function createAnalysisId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `analysis-${crypto.randomUUID()}`;
  }
  return `analysis-${Date.now()}`;
}

function safePercent(value: number) {
  return Math.max(0, Math.min(100, Math.round(value * 100)));
}

function buildColorFindings(pipeline: WoundAnalysisPipelineResult): ClinicalAnalysisResult['visualFindings'] {
  const features = pipeline.roiValidation.features;
  const candidates = [
    { label: 'vermelho/rosado', hex: '#dc2626', percentage: safePercent(features.redPinkRatio) },
    { label: 'amarelo/marrom', hex: '#d97706', percentage: safePercent(features.yellowBrownRatio) },
    { label: 'escuro', hex: '#27272a', percentage: safePercent(features.darkTissueRatio) },
    { label: 'palido/neutro', hex: '#e5e7eb', percentage: safePercent(features.paleTissueRatio + features.neutralBackgroundRatio * 0.35) }
  ].filter(item => item.percentage > 0);

  const tissueHints = pipeline.canAnalyze
    ? [
        'ROI aprovada pelo gate visual para analise assistiva limitada.',
        pipeline.tissueClassification.enabled
          ? 'Classificacao tecidual assistiva habilitada por modelo validado.'
          : pipeline.tissueClassification.reason
      ]
    : [pipeline.blockedReason || pipeline.roiValidation.reason];

  const attentionAreas = [
    ...pipeline.roiValidation.issues.map(issue => `Validacao ROI: ${issue}.`),
    pipeline.segmentation.limited && pipeline.segmentation.reason ? pipeline.segmentation.reason : ''
  ].filter(Boolean);

  return {
    dominantColors: candidates.sort((left, right) => right.percentage - left.percentage),
    tissueHints,
    attentionAreas,
    roiCoveragePercent: safePercent(pipeline.roiValidation.areaRatio)
  };
}

function buildConsideredData(options: {
  patient: Patient | null;
  assessment: Evaluation | null;
  rois: Roi[];
  history: Evaluation[];
  pipeline: WoundAnalysisPipelineResult;
}) {
  const considered = ['imagem clínica enviada', 'ROI manual normalizada'];
  if (options.pipeline.roiCrop) considered.push('recorte real da ROI');
  if (options.patient) considered.push('dados mínimos do paciente, sem telefone/e-mail no resultado');
  if (options.assessment) considered.push('dados estruturados da avaliação');
  if (options.history.length > 1) considered.push('histórico anterior do mesmo paciente/região');
  if (options.assessment?.notes) considered.push('observações clínicas');
  if (!options.pipeline.tissueClassification.enabled) considered.push('classificação tecidual bloqueada ou indisponível');
  return considered;
}

function buildAiSummary(pipeline: WoundAnalysisPipelineResult) {
  if (!pipeline.canAnalyze) {
    return 'A imagem analisada não apresenta evidência visual suficiente de ferida na ROI marcada. Para evitar resultado incorreto, o sistema não gerou classificação de tecido.';
  }

  if (!pipeline.tissueClassification.enabled) {
    return 'A ROI marcada apresenta características visuais compatíveis com área de ferida, com confiança moderada. A classificação tecidual automática está indisponível ou limitada e deve ser validada por profissional de saúde.';
  }

  return 'A ROI marcada passou pela validação visual e a classificação tecidual assistiva foi gerada por modelo habilitado, devendo ser interpretada com cautela e validação profissional.';
}

export async function buildClinicalAnalysisResult(options: BuildClinicalAnalysisOptions): Promise<ClinicalAnalysisResult> {
  const rois = ensureClinicalRois(options.rois).filter(roi => roi.points.length >= 3);
  const pipeline = await woundAnalysisPipeline.run({
    patient: options.patient,
    assessment: options.assessment,
    previousAssessments: options.history,
    image: options.image,
    rois
  });
  const evolution = buildWoundEvolution(options.assessment, options.history);
  const selectedRoiVersion = pipeline.selectedRoi?.roiVersion || rois[0]?.roiVersion || '2026-05-contextual';

  return {
    id: createAnalysisId(),
    patientId: options.patient?.id || options.assessment?.patientId,
    assessmentId: options.assessment?.id,
    imageId: options.imageId,
    roisUsed: rois,
    createdAt: new Date().toISOString(),
    createdBy: options.createdBy,
    mode: options.mode,
    analysisVersion: HEAL_ANALYZER_ANALYSIS_VERSION,
    roiVersion: selectedRoiVersion,
    canAnalyze: pipeline.canAnalyze,
    blockedReason: pipeline.blockedReason,
    imageQuality: pipeline.imageQuality,
    visualFindings: buildColorFindings(pipeline),
    roiValidation: {
      ...pipeline.roiValidation,
      features: { ...pipeline.roiValidation.features }
    },
    woundDetection: pipeline.woundDetection,
    segmentation: pipeline.segmentation,
    tissueClassification: pipeline.tissueClassification,
    clinicalContext: pipeline.clinicalContext,
    evolution,
    aiInference: {
      status: pipeline.analyzerResult ? 'completed' : pipeline.canAnalyze ? 'skipped' : 'skipped',
      modelVersion: pipeline.analyzerResult?.model_version || pipeline.woundDetection.modelVersion,
      confidence: pipeline.woundDetection.confidence,
      primaryTissue: pipeline.tissueClassification.enabled ? pipeline.tissueClassification.classes[0]?.label : undefined,
      summary: buildAiSummary(pipeline),
      error: pipeline.tissueClassification.enabled ? undefined : pipeline.tissueClassification.reason
    },
    alerts: pipeline.alerts,
    recommendations: pipeline.recommendations,
    consideredData: buildConsideredData({
      patient: options.patient,
      assessment: options.assessment,
      rois,
      history: options.history,
      pipeline
    }),
    disclaimer: HEAL_ANALYZER_DISCLAIMER
  };
}
