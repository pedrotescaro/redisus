import { describe, expect, it } from 'vitest';

import type { HealAnalyzerResult } from '../../services/ai/heal-analyzer-service';
import {
  applyServerSegmentation,
  type WoundSegmentationResult
} from '../../services/ai/woundSegmentationService';
import { classifyTissue } from '../../services/ai/tissueClassificationService';

describe('applyServerSegmentation', () => {
  it('substitui a prévia local pelo mapa clínico e preserva a incerteza', () => {
    const preview: WoundSegmentationResult = {
      method: 'heuristic_preview',
      limited: true,
      overlayUrl: 'data:image/png;base64,preview'
    };
    const result = {
      is_valid_wound: true,
      wound_area_px: 4200,
      tissues: [
        { name: 'Esfacelo', name_en: 'Slough (Fibrin)', percentage: 68 },
        { name: 'Granulação', name_en: 'Granulation Tissue', percentage: 17 }
      ],
      inference: { confidence: 0.82 },
      tissue_analysis_trace: { coverage_pct: 85, unclassified_pct: 15 },
      visuals: {
        segmentation: { data_url: 'data:image/png;base64,map' },
        combined: { data_url: 'data:image/jpeg;base64,combined' }
      }
    } as HealAnalyzerResult;

    const segmentation = applyServerSegmentation(preview, result);

    expect(segmentation.method).toBe('clinical_backend');
    expect(segmentation.overlayUrl).toBe('data:image/jpeg;base64,combined');
    expect(segmentation.maskUrl).toBe('data:image/png;base64,map');
    expect(segmentation.coveragePercent).toBe(85);
    expect(segmentation.unclassifiedPercent).toBe(15);
    expect(segmentation.computedPercentages?.slough_fibrin).toBe(68);
    expect(segmentation.computedPercentages?.granulation).toBe(17);

    const classification = classifyTissue({
      detection: {
        hasWound: true,
        confidence: 0.9,
        reason: 'ROI aprovada',
        mode: 'roi_validation_gate',
        modelVersion: 'roi-gate'
      },
      segmentation,
      analyzerResult: result
    });

    expect(classification.enabled).toBe(true);
    expect(classification.reason).toContain('experimental');
    expect(classification.classes[0].confidence).toBeLessThanOrEqual(0.45);
  });
});
