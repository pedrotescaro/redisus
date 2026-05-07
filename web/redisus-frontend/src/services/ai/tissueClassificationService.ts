import type { HealAnalyzerResult } from './heal-analyzer-service';
import type { WoundDetectionResult } from './woundDetectionService';
import type { WoundSegmentationResult } from './woundSegmentationService';

export type TissueClassLabel = 'granulation' | 'slough_fibrin' | 'necrosis' | 'epithelial' | 'unknown';

export interface TissueClassificationEntry {
  label: TissueClassLabel;
  percentage: number;
  confidence: number;
}

export interface TissueClassificationResult {
  enabled: boolean;
  classes: TissueClassificationEntry[];
  reason: string;
  modelVersion?: string;
}

const VALIDATED_TISSUE_MODEL_ENABLED =
  import.meta.env.VITE_HEAL_ANALYZER_ENABLE_VALIDATED_TISSUE_MODEL === 'true';

function normalizeLabel(name: string): TissueClassLabel {
  const value = name
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();

  if (value.includes('granulation') || value.includes('granulacao')) return 'granulation';
  if (value.includes('slough') || value.includes('esfacelo') || value.includes('fibrin')) return 'slough_fibrin';
  if (value.includes('necros')) return 'necrosis';
  if (value.includes('epithel') || value.includes('epitel')) return 'epithelial';
  return 'unknown';
}

function isValidatedServerResult(result: HealAnalyzerResult | null | undefined) {
  if (!result) return false;
  const modelVersion = String(result.model_version || '');
  return (
    result.is_valid_wound === true &&
    result.inference?.fallback_used === false &&
    Number(result.inference?.confidence || 0) >= 0.8 &&
    modelVersion.length > 0 &&
    !modelVersion.toLowerCase().includes('fallback')
  );
}

export function classifyTissue(options: {
  detection: WoundDetectionResult;
  segmentation: WoundSegmentationResult;
  analyzerResult?: HealAnalyzerResult | null;
}): TissueClassificationResult {
  if (!options.detection.hasWound) {
    return {
      enabled: false,
      classes: [],
      reason: 'Classificacao tecidual bloqueada porque a ROI nao contem evidencia visual suficiente de ferida.'
    };
  }

  if (!VALIDATED_TISSUE_MODEL_ENABLED) {
    return {
      enabled: false,
      classes: [],
      reason:
        'Classificacao tecidual indisponivel: esta instalacao nao possui modelo de tecido treinado, validado e habilitado para uso clinico assistivo.'
    };
  }

  if (!isValidatedServerResult(options.analyzerResult)) {
    return {
      enabled: false,
      classes: [],
      reason:
        'Classificacao tecidual bloqueada porque a inferencia disponivel esta em fallback, baixa confianca ou sem validacao suficiente.'
    };
  }

  const confidence = Number(options.analyzerResult?.inference?.confidence || 0);
  const classMap = new Map<TissueClassLabel, TissueClassificationEntry>();

  for (const tissue of options.analyzerResult?.tissues || []) {
    const label = normalizeLabel(`${tissue.name} ${tissue.name_en}`);
    if (label === 'unknown') continue;
    const current = classMap.get(label) || { label, percentage: 0, confidence };
    current.percentage += Number(tissue.percentage || 0);
    current.confidence = Math.min(current.confidence, confidence);
    classMap.set(label, current);
  }

  const classes = [...classMap.values()]
    .map(entry => ({
      ...entry,
      percentage: Math.max(0, Math.min(100, Math.round(entry.percentage)))
    }))
    .filter(entry => entry.percentage > 0)
    .sort((left, right) => right.percentage - left.percentage);

  if (!classes.length) {
    return {
      enabled: false,
      classes: [],
      reason: 'O modelo validado nao retornou distribuicao tecidual utilizavel para esta ROI.'
    };
  }

  return {
    enabled: true,
    classes,
    reason: 'Classificacao tecidual assistiva habilitada por modelo validado e ROI aprovada.',
    modelVersion: options.analyzerResult?.model_version
  };
}
