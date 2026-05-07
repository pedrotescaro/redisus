import { ROI_COLORS } from './constants';
import type { Roi, RoiPoint, RoiType } from './types';

export const clamp01 = (value: unknown) => Math.min(Math.max(Number(value) || 0, 0), 1);

export const normalizeRoiPoints = (points: unknown): RoiPoint[] =>
  Array.isArray(points)
    ? points.map(point => ({ x: clamp01(point?.x), y: clamp01(point?.y) }))
    : [];

export const createRoi = (index: number, type: RoiType = 'polygon'): Roi => ({
  id: `roi-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  label: `Ferida ${index + 1}`,
  type,
  points: [],
  color: ROI_COLORS[index % ROI_COLORS.length],
  createdAt: new Date().toISOString(),
  normalized: true,
  roiVersion: '2026-05-contextual'
});

export const normalizeRois = (rois: unknown): Roi[] =>
  Array.isArray(rois)
    ? rois
        .map((roi, index): Roi => ({
          id: String(roi?.id || `roi-${index + 1}`),
          label: String(roi?.label || `Ferida ${index + 1}`),
          type: roi?.type === 'circle' ? 'circle' : roi?.type === 'freehand' || roi?.mode === 'pen' ? 'freehand' : 'polygon',
          points: normalizeRoiPoints(roi?.points),
          color: String(roi?.color || ROI_COLORS[index % ROI_COLORS.length]),
          createdAt: String(roi?.createdAt || new Date().toISOString()),
          normalized: true,
          updatedAt: typeof roi?.updatedAt === 'string' ? roi.updatedAt : undefined,
          createdBy: typeof roi?.createdBy === 'string' ? roi.createdBy : undefined,
          updatedBy: typeof roi?.updatedBy === 'string' ? roi.updatedBy : undefined,
          roiVersion: String(roi?.roiVersion || '2026-05-contextual'),
          imageId: typeof roi?.imageId === 'string' ? roi.imageId : undefined,
          assessmentId: typeof roi?.assessmentId === 'string' ? roi.assessmentId : undefined,
          patientId: typeof roi?.patientId === 'string' ? roi.patientId : undefined,
          verifiedByProfessional: Boolean(roi?.verifiedByProfessional),
          consentForResearch: Boolean(roi?.consentForResearch),
          anonymizedExportReady: Boolean(roi?.anonymizedExportReady)
        }))
        .filter(roi => roi.points.length > 0)
    : [];

export const hasValidRoi = (roi: Roi) => roi.points.length >= 3;
export const hasValidRois = (rois: Roi[]) => rois.some(hasValidRoi);

export const roiPointsToSvgPoints = (points: RoiPoint[]) =>
  normalizeRoiPoints(points)
    .map(point => `${point.x * 1000},${point.y * 1000}`)
    .join(' ');

export const roiPointsToPath = (points: RoiPoint[]) => {
  const normalized = normalizeRoiPoints(points);
  if (!normalized.length) return '';
  const [first, ...rest] = normalized.map(point => ({ x: point.x * 1000, y: point.y * 1000 }));
  return `M ${first.x} ${first.y} ${rest.map(point => `L ${point.x} ${point.y}`).join(' ')}`;
};

export const estimatePolygonAreaPercent = (points: RoiPoint[]) => {
  const normalized = normalizeRoiPoints(points);
  if (normalized.length < 3) return 0;
  const area = normalized.reduce((sum, point, index) => {
    const next = normalized[(index + 1) % normalized.length];
    return sum + point.x * next.y - next.x * point.y;
  }, 0);
  return Math.abs(area / 2) * 100;
};

export const estimateRoisAreaPercent = (rois: Roi[]) =>
  normalizeRois(rois).reduce((sum, roi) => sum + estimatePolygonAreaPercent(roi.points), 0);
