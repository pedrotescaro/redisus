import { describe, expect, it } from 'vitest';

import { estimatePolygonAreaPercent, normalizeRoiPoints, normalizeRois } from '../../lib/roi';

describe('ROI', () => {
  it('normaliza pontos entre 0 e 1', () => {
    expect(normalizeRoiPoints([{ x: -1, y: 2 }, { x: 0.25, y: 0.75 }])).toEqual([
      { x: 0, y: 1 },
      { x: 0.25, y: 0.75 }
    ]);
  });

  it('normaliza formato legado do mobile', () => {
    const [roi] = normalizeRois([{ mode: 'pen', points: [{ x: 0.1, y: 0.2 }] }]);
    expect(roi.type).toBe('freehand');
    expect(roi.label).toBe('Ferida 1');
  });

  it('calcula area aproximada da ROI', () => {
    const area = estimatePolygonAreaPercent([
      { x: 0, y: 0 },
      { x: 1, y: 0 },
      { x: 1, y: 1 },
      { x: 0, y: 1 }
    ]);
    expect(area).toBe(100);
  });
});
