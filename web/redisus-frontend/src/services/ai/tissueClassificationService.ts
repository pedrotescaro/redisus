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

const LOCAL_MODE = import.meta.env.VITE_HEAL_ANALYZER_LOCAL_MODE === 'true';

function isValidatedServerResult(result: HealAnalyzerResult | null | undefined) {
  if (!result) return false;

  if (LOCAL_MODE && result.is_valid_wound === true) {
    return true;
  }

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

  // Prioriza a leitura clinica do backend. Resultados nao validados
  // permanecem explicitamente experimentais e com confianca conservadora.
  if (options.analyzerResult?.is_valid_wound) {
    const validated = isValidatedServerResult(options.analyzerResult);
    const measuredConfidence = Number(options.analyzerResult?.inference?.confidence || 0);
    const coverage = Number(options.analyzerResult?.tissue_analysis_trace?.coverage_pct || 0) / 100;
    const confidence = validated
      ? measuredConfidence
      : Math.min(0.45, Math.max(0.2, coverage * 0.45));
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

    if (classes.length > 0) {
      return {
        enabled: true,
        classes,
        reason: validated
          ? 'Classificacao tecidual assistiva habilitada por modelo validado e ROI aprovada.'
          : 'Classificacao tecidual experimental produzida pelo backend clinico; requer revisao profissional.',
        modelVersion: options.analyzerResult?.model_version
      };
    }
  }

  // Fallback to client-side TypeScript classification
  if (VALIDATED_TISSUE_MODEL_ENABLED && options.segmentation.computedPercentages) {
    const p = options.segmentation.computedPercentages;
    const classes = [
      { label: 'granulation' as TissueClassLabel, percentage: Math.round(p.granulation), confidence: 0.45 },
      { label: 'slough_fibrin' as TissueClassLabel, percentage: Math.round(p.slough_fibrin), confidence: 0.45 },
      { label: 'necrosis' as TissueClassLabel, percentage: Math.round(p.necrosis), confidence: 0.45 },
      { label: 'epithelial' as TissueClassLabel, percentage: Math.round(p.epithelial), confidence: 0.45 }
    ].filter(c => c.percentage > 0)
     .sort((left, right) => right.percentage - left.percentage);

    return {
      enabled: true,
      classes,
      reason: 'Classificacao tecidual local habilitada explicitamente para validacao controlada.',
      modelVersion: 'HEAL Client Heuristic Preview'
    };
  }

  return {
    enabled: false,
    classes: [],
    reason:
      'Classificacao tecidual indisponivel: esta instalacao nao possui modelo de tecido treinado, validado e habilitado.'
  };
}
