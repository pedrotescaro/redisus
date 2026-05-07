import { HEAL_ANALYZER_ROI_VERSION, buildHealAnalyzerRoiSelection, type HealAnalyzerRoiSelection } from '../../lib/heal-analyzer-roi';
import { ROI_COLORS } from '../../lib/constants';
import { normalizeRois } from '../../lib/roi';
import type { Roi, RoiPoint } from '../../lib/types';

export const ROI_VERSION = '2026-05-contextual';

export interface RoiVisualFindings {
  dominantColors: Array<{ label: string; hex: string; percentage: number }>;
  tissueHints: string[];
  attentionAreas: string[];
  roiCoveragePercent: number;
}

function createRoiId(index: number) {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `roi-${crypto.randomUUID()}`;
  }
  return `roi-${Date.now()}-${index}`;
}

function selectionToolToRoiType(selection: HealAnalyzerRoiSelection): Roi['type'] {
  if (selection.tool === 'circle') return 'circle';
  if (selection.tool === 'freehand') return 'freehand';
  return 'polygon';
}

export function roiToAnalyzerSelection(roi: Roi): HealAnalyzerRoiSelection {
  const tool = roi.type === 'circle' ? 'circle' : roi.type === 'freehand' ? 'freehand' : 'polygon';
  return {
    ...buildHealAnalyzerRoiSelection(tool, roi.points, 1, 1),
    version: roi.roiVersion || HEAL_ANALYZER_ROI_VERSION,
    confirmed: roi.points.length >= 3
  };
}

export function roisToAnalyzerSelections(rois: Roi[]) {
  return normalizeRois(rois)
    .filter(roi => roi.points.length >= 3)
    .map(roiToAnalyzerSelection);
}

export function analyzerSelectionToRoi(selection: HealAnalyzerRoiSelection, index: number, previous?: Roi): Roi {
  const now = new Date().toISOString();
  return {
    id: previous?.id || createRoiId(index),
    label: previous?.label || `Ferida principal ${index + 1}`,
    type: selectionToolToRoiType(selection),
    points: selection.points,
    color: previous?.color || ROI_COLORS[index % ROI_COLORS.length],
    createdAt: previous?.createdAt || now,
    updatedAt: now,
    normalized: true,
    roiVersion: ROI_VERSION
  };
}

export function analyzerSelectionsToRois(selections: HealAnalyzerRoiSelection[], previous: Roi[] = []) {
  return selections.map((selection, index) => analyzerSelectionToRoi(selection, index, previous[index]));
}

export function ensureClinicalRois(rois: unknown) {
  return normalizeRois(rois).map((roi, index) => ({
    ...roi,
    label: roi.label || `Ferida principal ${index + 1}`,
    normalized: true as const,
    roiVersion: roi.roiVersion || ROI_VERSION
  }));
}

function pointInPolygon(point: RoiPoint, polygon: RoiPoint[]) {
  let inside = false;
  for (let index = 0, previous = polygon.length - 1; index < polygon.length; previous = index++) {
    const currentPoint = polygon[index];
    const previousPoint = polygon[previous];
    const intersects =
      currentPoint.y > point.y !== previousPoint.y > point.y &&
      point.x <
        ((previousPoint.x - currentPoint.x) * (point.y - currentPoint.y)) /
          (previousPoint.y - currentPoint.y || Number.EPSILON) +
          currentPoint.x;
    if (intersects) inside = !inside;
  }
  return inside;
}

function rgbToHex(red: number, green: number, blue: number) {
  return `#${[red, green, blue].map(value => value.toString(16).padStart(2, '0')).join('')}`;
}

function colorBucket(red: number, green: number, blue: number) {
  if (red > 120 && green < 110 && blue < 110) return { label: 'avermelhado', hint: 'Area avermelhada detectada na ROI; achado visual nao diagnostico.' };
  if (red > 130 && green > 110 && blue < 95) return { label: 'amarelado', hint: 'Area amarelada detectada na ROI; nao classificar tecido sem modelo validado.' };
  if (red < 75 && green < 75 && blue < 75) return { label: 'escurecido', hint: 'Area escurecida detectada na ROI; exige correlacao com exame fisico.' };
  if (red > 170 && green > 170 && blue > 160) return { label: 'esbranquicado', hint: 'Area esbranquicada pode refletir brilho, gaze, pele clara ou outro artefato visual.' };
  return { label: 'misto', hint: 'Padrao de cor misto na ROI, sem classificacao tecidual automatica.' };
}

async function loadImage(source: File | string) {
  const imageUrl = typeof source === 'string' ? source : URL.createObjectURL(source);
  const image = new Image();
  image.crossOrigin = 'anonymous';

  try {
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error('Nao foi possivel carregar a imagem para processamento visual.'));
      image.src = imageUrl;
    });
  } finally {
    if (typeof source !== 'string') URL.revokeObjectURL(imageUrl);
  }

  return image;
}

export async function analyzeRoiVisualFindings(source: File | string | null, rois: Roi[]): Promise<RoiVisualFindings> {
  const validRois = ensureClinicalRois(rois).filter(roi => roi.points.length >= 3);
  const fallback: RoiVisualFindings = {
    dominantColors: [],
    tissueHints: validRois.length ? [] : ['Analise visual limitada pela ausencia de ROI manual.'],
    attentionAreas: validRois.length ? [] : ['Crie uma ROI para concentrar a leitura na area da ferida.'],
    roiCoveragePercent: 0
  };

  if (!source || !validRois.length) return fallback;

  try {
    const image = await loadImage(source);
    const width = Math.min(image.naturalWidth || image.width, 720);
    const scale = width / Math.max(image.naturalWidth || image.width, 1);
    const height = Math.max(1, Math.round((image.naturalHeight || image.height) * scale));
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext('2d', { willReadFrequently: true });
    if (!context) return fallback;
    context.drawImage(image, 0, 0, width, height);
    const imageData = context.getImageData(0, 0, width, height).data;
    const buckets = new Map<string, { count: number; red: number; green: number; blue: number; hint: string }>();
    let sampled = 0;
    let covered = 0;

    for (let y = 0; y < height; y += 4) {
      for (let x = 0; x < width; x += 4) {
        const normalizedPoint = { x: x / width, y: y / height };
        const inRoi = validRois.some(roi => pointInPolygon(normalizedPoint, roi.points));
        if (!inRoi) continue;
        covered += 1;
        const offset = (y * width + x) * 4;
        const red = imageData[offset];
        const green = imageData[offset + 1];
        const blue = imageData[offset + 2];
        const bucket = colorBucket(red, green, blue);
        const current = buckets.get(bucket.label) || { count: 0, red: 0, green: 0, blue: 0, hint: bucket.hint };
        buckets.set(bucket.label, {
          count: current.count + 1,
          red: current.red + red,
          green: current.green + green,
          blue: current.blue + blue,
          hint: bucket.hint
        });
        sampled += 1;
      }
    }

    if (!sampled) return fallback;

    const dominantColors = [...buckets.entries()]
      .map(([label, bucket]) => ({
        label,
        hex: rgbToHex(Math.round(bucket.red / bucket.count), Math.round(bucket.green / bucket.count), Math.round(bucket.blue / bucket.count)),
        percentage: Math.round((bucket.count / sampled) * 100)
      }))
      .sort((left, right) => right.percentage - left.percentage);

    const tissueHints = dominantColors
      .map(color => buckets.get(color.label)?.hint)
      .filter((hint): hint is string => Boolean(hint))
      .slice(0, 4);

    const attentionAreas = dominantColors
      .filter(color => ['amarelado', 'escurecido', 'esbranquicado'].includes(color.label) && color.percentage >= 8)
      .map(color => `${color.percentage}% da ROI ficou em faixa visual ${color.label}.`);

    return {
      dominantColors,
      tissueHints,
      attentionAreas,
      roiCoveragePercent: Math.round((covered / ((width / 4) * (height / 4))) * 100)
    };
  } catch {
    return fallback;
  }
}
