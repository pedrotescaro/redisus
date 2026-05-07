import { computePolygonArea } from '../../lib/heal-analyzer-roi';
import { normalizeRoiPoints } from '../../lib/roi';
import type { Roi, RoiPoint } from '../../lib/types';

export interface NormalizedBoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface RoiCropResult {
  roi: Roi | null;
  roiPoints: RoiPoint[];
  cropRoiPoints: RoiPoint[];
  boundingBox: NormalizedBoundingBox;
  areaPixels: number;
  areaRatio: number;
  width: number;
  height: number;
  originalWidth: number;
  originalHeight: number;
  canvas: HTMLCanvasElement;
  maskedCanvas: HTMLCanvasElement;
  imageData: ImageData;
  mask: Uint8ClampedArray;
  dataUrl: string;
  maskedDataUrl: string;
  file: File;
}

function clamp01(value: number) {
  return Math.min(1, Math.max(0, Number.isFinite(value) ? value : 0));
}

function buildBoundingBox(points: RoiPoint[]): NormalizedBoundingBox {
  if (!points.length) return { x: 0, y: 0, width: 0, height: 0 };

  const xs = points.map(point => clamp01(point.x));
  const ys = points.map(point => clamp01(point.y));
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);

  return {
    x: minX,
    y: minY,
    width: Math.max(0, maxX - minX),
    height: Math.max(0, maxY - minY)
  };
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

async function loadImage(source: File | string) {
  const imageUrl = typeof source === 'string' ? source : URL.createObjectURL(source);
  const image = new Image();
  image.crossOrigin = 'anonymous';

  try {
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error('Nao foi possivel carregar a imagem para recorte da ROI.'));
      image.src = imageUrl;
    });
  } finally {
    if (typeof source !== 'string') URL.revokeObjectURL(imageUrl);
  }

  return image;
}

async function canvasToFile(canvas: HTMLCanvasElement, fileName: string) {
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(result => (result ? resolve(result) : reject(new Error('Nao foi possivel gerar o recorte da ROI.'))), 'image/jpeg', 0.92);
  });
  return new File([blob], fileName, { type: 'image/jpeg' });
}

function drawPolygonPath(context: CanvasRenderingContext2D, points: RoiPoint[]) {
  if (!points.length) return;
  context.beginPath();
  context.moveTo(points[0].x, points[0].y);
  for (const point of points.slice(1)) {
    context.lineTo(point.x, point.y);
  }
  context.closePath();
}

function buildCropRoiPoints(points: RoiPoint[], box: NormalizedBoundingBox): RoiPoint[] {
  return points.map(point => ({
    x: box.width > 0 ? clamp01((point.x - box.x) / box.width) : 0,
    y: box.height > 0 ? clamp01((point.y - box.y) / box.height) : 0
  }));
}

export async function cropImageByNormalizedRoi(source: File | string, roiPoints: RoiPoint[], roi: Roi | null = null): Promise<RoiCropResult> {
  const points = normalizeRoiPoints(roiPoints);
  if (points.length < 3) {
    throw new Error('ROI invalida: marque ao menos tres pontos normalizados entre 0 e 1.');
  }

  const boundingBox = buildBoundingBox(points);
  if (boundingBox.width <= 0 || boundingBox.height <= 0) {
    throw new Error('ROI invalida: a area marcada nao forma um recorte utilizavel.');
  }

  const image = await loadImage(source);
  const originalWidth = image.naturalWidth || image.width;
  const originalHeight = image.naturalHeight || image.height;
  const sourceX = Math.max(0, Math.round(boundingBox.x * originalWidth));
  const sourceY = Math.max(0, Math.round(boundingBox.y * originalHeight));
  const sourceWidth = Math.max(1, Math.round(boundingBox.width * originalWidth));
  const sourceHeight = Math.max(1, Math.round(boundingBox.height * originalHeight));
  const cropRoiPoints = buildCropRoiPoints(points, boundingBox);
  const pixelRoiPoints = cropRoiPoints.map(point => ({ x: point.x * sourceWidth, y: point.y * sourceHeight }));

  const canvas = document.createElement('canvas');
  canvas.width = sourceWidth;
  canvas.height = sourceHeight;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  if (!context) throw new Error('Canvas indisponivel para recortar a ROI.');
  context.drawImage(image, sourceX, sourceY, sourceWidth, sourceHeight, 0, 0, sourceWidth, sourceHeight);

  const imageData = context.getImageData(0, 0, sourceWidth, sourceHeight);
  const mask = new Uint8ClampedArray(sourceWidth * sourceHeight);
  let areaPixels = 0;
  for (let y = 0; y < sourceHeight; y += 1) {
    for (let x = 0; x < sourceWidth; x += 1) {
      const inside = pointInPolygon({ x: x / sourceWidth, y: y / sourceHeight }, cropRoiPoints);
      if (!inside) continue;
      mask[y * sourceWidth + x] = 255;
      areaPixels += 1;
    }
  }

  const maskedCanvas = document.createElement('canvas');
  maskedCanvas.width = sourceWidth;
  maskedCanvas.height = sourceHeight;
  const maskedContext = maskedCanvas.getContext('2d');
  if (!maskedContext) throw new Error('Canvas indisponivel para mascarar a ROI.');
  maskedContext.fillStyle = '#ffffff';
  maskedContext.fillRect(0, 0, sourceWidth, sourceHeight);
  maskedContext.save();
  drawPolygonPath(maskedContext, pixelRoiPoints);
  maskedContext.clip();
  maskedContext.drawImage(canvas, 0, 0);
  maskedContext.restore();

  const sourceName = source instanceof File ? source.name.replace(/\.[^.]+$/, '') : 'assessment-image';
  const areaRatio = computePolygonArea(points);

  return {
    roi,
    roiPoints: points,
    cropRoiPoints,
    boundingBox,
    areaPixels,
    areaRatio,
    width: sourceWidth,
    height: sourceHeight,
    originalWidth,
    originalHeight,
    canvas,
    maskedCanvas,
    imageData,
    mask,
    dataUrl: canvas.toDataURL('image/jpeg', 0.9),
    maskedDataUrl: maskedCanvas.toDataURL('image/jpeg', 0.9),
    file: await canvasToFile(maskedCanvas, `roi-${sourceName}.jpg`)
  };
}

export async function cropImageByRoi(source: File | string, roi: Roi): Promise<RoiCropResult> {
  return cropImageByNormalizedRoi(source, roi.points, roi);
}
