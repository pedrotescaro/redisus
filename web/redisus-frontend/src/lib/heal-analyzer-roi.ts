export const HEAL_ANALYZER_ROI_VERSION = "2026-04-17";

export type HealAnalyzerRoiTool = "polygon" | "freehand" | "circle";

export type HealAnalyzerRoiPoint = {
  x: number;
  y: number;
};

export type HealAnalyzerRoiBoundingBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type HealAnalyzerRoiSelection = {
  version: string;
  tool: HealAnalyzerRoiTool;
  points: HealAnalyzerRoiPoint[];
  bounding_box: HealAnalyzerRoiBoundingBox;
  area_ratio: number;
  confirmed: boolean;
  image_width: number;
  image_height: number;
  source?: "manual" | "automatic";
  area_px?: number;
  analysis_width?: number;
  analysis_height?: number;
  analysis_bounding_box?: HealAnalyzerRoiBoundingBox;
  storage_path?: string | null;
};

export type HealAnalyzerRoiSummary = Partial<HealAnalyzerRoiSelection> & {
  selection_count?: number;
  tools?: string[];
};

export type HealAnalyzerRoiRequestPayload = Pick<
  HealAnalyzerRoiSelection,
  | "version"
  | "tool"
  | "points"
  | "bounding_box"
  | "area_ratio"
  | "confirmed"
  | "image_width"
  | "image_height"
>;

export function clampNormalized(value: number) {
  if (Number.isNaN(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

export function clampPoint(point: HealAnalyzerRoiPoint): HealAnalyzerRoiPoint {
  return {
    x: clampNormalized(point.x),
    y: clampNormalized(point.y),
  };
}

export function distanceBetweenPoints(
  left: HealAnalyzerRoiPoint,
  right: HealAnalyzerRoiPoint,
) {
  return Math.hypot(left.x - right.x, left.y - right.y);
}

export function approximateEllipseAsPolygon(
  start: HealAnalyzerRoiPoint,
  end: HealAnalyzerRoiPoint,
  segments = 48,
) {
  const centerX = (start.x + end.x) / 2;
  const centerY = (start.y + end.y) / 2;
  const radiusX = Math.abs(end.x - start.x) / 2;
  const radiusY = Math.abs(end.y - start.y) / 2;

  if (radiusX <= 0 || radiusY <= 0) return [];

  return Array.from({ length: segments }, (_, index) => {
    const angle = (index / segments) * Math.PI * 2;
    return clampPoint({
      x: centerX + radiusX * Math.cos(angle),
      y: centerY + radiusY * Math.sin(angle),
    });
  });
}

export function computeRoiBoundingBox(points: HealAnalyzerRoiPoint[]) {
  if (!points.length) {
    return { x: 0, y: 0, width: 0, height: 0 };
  }

  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);

  return {
    x: clampNormalized(minX),
    y: clampNormalized(minY),
    width: clampNormalized(maxX - minX),
    height: clampNormalized(maxY - minY),
  };
}

export function computePolygonArea(points: HealAnalyzerRoiPoint[]) {
  if (points.length < 3) return 0;

  let area = 0;
  for (let index = 0; index < points.length; index += 1) {
    const current = points[index];
    const next = points[(index + 1) % points.length];
    area += current.x * next.y - next.x * current.y;
  }

  return Math.abs(area) / 2;
}

export function buildHealAnalyzerRoiSelection(
  tool: HealAnalyzerRoiTool,
  points: HealAnalyzerRoiPoint[],
  imageWidth: number,
  imageHeight: number,
): HealAnalyzerRoiSelection {
  const normalizedPoints = points.map(clampPoint);
  return {
    version: HEAL_ANALYZER_ROI_VERSION,
    tool,
    points: normalizedPoints,
    bounding_box: computeRoiBoundingBox(normalizedPoints),
    area_ratio: computePolygonArea(normalizedPoints),
    confirmed: true,
    image_width: imageWidth,
    image_height: imageHeight,
    source: "manual",
  };
}

export function isHealAnalyzerRoiSelection(
  value: unknown,
): value is HealAnalyzerRoiSelection {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Partial<HealAnalyzerRoiSelection>;
  return (
    typeof candidate.version === "string" &&
    (candidate.tool === "polygon" ||
      candidate.tool === "freehand" ||
      candidate.tool === "circle") &&
    Array.isArray(candidate.points) &&
    typeof candidate.image_width === "number" &&
    typeof candidate.image_height === "number"
  );
}

export function toHealAnalyzerRoiRequestPayload(
  selection: HealAnalyzerRoiSelection,
): HealAnalyzerRoiRequestPayload {
  return {
    version: selection.version,
    tool: selection.tool,
    points: selection.points.map(clampPoint),
    bounding_box: {
      x: clampNormalized(selection.bounding_box.x),
      y: clampNormalized(selection.bounding_box.y),
      width: clampNormalized(selection.bounding_box.width),
      height: clampNormalized(selection.bounding_box.height),
    },
    area_ratio: clampNormalized(selection.area_ratio),
    confirmed: selection.confirmed,
    image_width: selection.image_width,
    image_height: selection.image_height,
  };
}

export function toHealAnalyzerRoiRequestPayloads(
  selections: HealAnalyzerRoiSelection[],
) {
  return selections.map(toHealAnalyzerRoiRequestPayload);
}

export function roiToolLabel(tool: HealAnalyzerRoiTool) {
  if (tool === "polygon") return "Poligono";
  if (tool === "freehand") return "Desenho livre";
  return "Circulo";
}
