/* eslint-disable @next/next/no-img-element */
"use client";

import type { PointerEvent as ReactPointerEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2,
  Circle,
  Eraser,
  Maximize2,
  Minus,
  MousePointer2,
  PenTool,
  PencilLine,
  Plus,
  PlusCircle,
  Redo2,
  Save,
  Undo2,
} from "lucide-react";
import {
  approximateEllipseAsPolygon,
  buildHealAnalyzerRoiSelection,
  clampPoint,
  distanceBetweenPoints,
  roiToolLabel,
  type HealAnalyzerRoiPoint,
  type HealAnalyzerRoiSelection,
  type HealAnalyzerRoiTool,
} from "../../lib/heal-analyzer-roi";
import { cn } from "../../lib/utils";

export type WoundRoiCanvasProps = {
  activeSavedSelectionIndex?: number | null;
  confirmLabel?: string;
  disabled?: boolean;
  imageSrc: string;
  initialSelection?: HealAnalyzerRoiSelection | null;
  savedSelections?: HealAnalyzerRoiSelection[];
  onConfirm: (selection: HealAnalyzerRoiSelection) => void;
  onSelectionCleared: () => void;
};

type CircleDraft = {
  current: HealAnalyzerRoiPoint;
  start: HealAnalyzerRoiPoint;
};

const TOOL_OPTIONS: Array<{ description: string; tool: HealAnalyzerRoiTool }> = [
  {
    tool: "polygon",
    description: "Clique nos pontos da borda e feche o contorno com precisao.",
  },
  {
    tool: "freehand",
    description: "Desenhe a área da lesão em um traço contínuo.",
  },
  {
    tool: "circle",
    description: "Arraste para criar um circulo/ovalo rapido sobre a ferida.",
  },
];

const TOOL_ICONS = {
  polygon: MousePointer2,
  freehand: PenTool,
  circle: Circle,
} satisfies Record<HealAnalyzerRoiTool, typeof MousePointer2>;

const SAVED_SELECTION_COLORS = [
  "#22c55e",
  "#38bdf8",
  "#f97316",
  "#e879f9",
  "#facc15",
  "#a78bfa",
];

function toSvgCoordinate(value: number) {
  return value * 100;
}

function toSvgPoints(points: HealAnalyzerRoiPoint[]) {
  return points
    .map((point) => `${toSvgCoordinate(point.x)},${toSvgCoordinate(point.y)}`)
    .join(" ");
}

export function WoundRoiCanvas({
  activeSavedSelectionIndex = null,
  confirmLabel = "Confirmar ROI",
  disabled = false,
  imageSrc,
  initialSelection = null,
  savedSelections = [],
  onConfirm,
  onSelectionCleared,
}: WoundRoiCanvasProps) {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const activePointerIdRef = useRef<number | null>(null);
  const [zoom, setZoom] = useState(1);
  const [tool, setTool] = useState<HealAnalyzerRoiTool>(
    initialSelection?.tool ?? "polygon",
  );
  const [imageSize, setImageSize] = useState({ height: 0, width: 0 });
  const [points, setPoints] = useState<HealAnalyzerRoiPoint[]>(
    initialSelection?.points ?? [],
  );
  const [polygonClosed, setPolygonClosed] = useState(
    Boolean(initialSelection?.points?.length),
  );
  const [confirmed, setConfirmed] = useState(Boolean(initialSelection?.confirmed));
  const [isDrawing, setIsDrawing] = useState(false);
  const [circleDraft, setCircleDraft] = useState<CircleDraft | null>(null);
  const [draggingVertexIndex, setDraggingVertexIndex] = useState<number | null>(null);

  useEffect(() => {
    setTool(initialSelection?.tool ?? "polygon");
    setPoints(initialSelection?.points ?? []);
    setPolygonClosed(Boolean(initialSelection?.points?.length));
    setConfirmed(Boolean(initialSelection?.confirmed));
    setCircleDraft(null);
    setIsDrawing(false);
    setDraggingVertexIndex(null);
    activePointerIdRef.current = null;
    setZoom(1);
  }, [imageSrc, initialSelection]);

  const previewPoints = useMemo(() => {
    if (circleDraft) {
      return approximateEllipseAsPolygon(circleDraft.start, circleDraft.current);
    }
    return points;
  }, [circleDraft, points]);

  const visibleSavedSelections = useMemo(
    () =>
      savedSelections
        .map((selection, index) => ({ selection, index }))
        .filter((item) => item.index !== activeSavedSelectionIndex),
    [activeSavedSelectionIndex, savedSelections],
  );

  const selectionReady =
    previewPoints.length >= 3 && (tool !== "polygon" || polygonClosed || Boolean(circleDraft));
  const areaPercent = selectionReady
    ? Math.round(
        buildHealAnalyzerRoiSelection(
          tool,
          previewPoints,
          Math.max(imageSize.width, 1),
          Math.max(imageSize.height, 1),
        ).area_ratio * 100,
      )
    : 0;

  const markSelectionDirty = () => {
    setConfirmed(false);
  };

  const resetSelection = (notifyParent = false) => {
    setPoints([]);
    setPolygonClosed(false);
    setCircleDraft(null);
    setIsDrawing(false);
    setDraggingVertexIndex(null);
    activePointerIdRef.current = null;
    setConfirmed(false);
    if (notifyParent) {
      onSelectionCleared();
    }
  };

  const getNormalizedPoint = (event: ReactPointerEvent<SVGSVGElement>) => {
    const bounds = svgRef.current?.getBoundingClientRect();
    if (!bounds || bounds.width <= 0 || bounds.height <= 0) {
      return { x: 0, y: 0 };
    }

    return clampPoint({
      x: (event.clientX - bounds.left) / bounds.width,
      y: (event.clientY - bounds.top) / bounds.height,
    });
  };

  const handleToolChange = (nextTool: HealAnalyzerRoiTool) => {
    if (disabled || nextTool === tool) return;
    setTool(nextTool);
    resetSelection(false);
  };

  const handleOverlayPointerDown = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (disabled || confirmed) return;

    const point = getNormalizedPoint(event);

    if (tool === "freehand") {
      markSelectionDirty();
      activePointerIdRef.current = event.pointerId;
      svgRef.current?.setPointerCapture(event.pointerId);
      setIsDrawing(true);
      setPolygonClosed(true);
      setCircleDraft(null);
      setPoints([point]);
      return;
    }

    if (tool === "circle") {
      markSelectionDirty();
      activePointerIdRef.current = event.pointerId;
      svgRef.current?.setPointerCapture(event.pointerId);
      setIsDrawing(true);
      setCircleDraft({ start: point, current: point });
      return;
    }
  };

  const handleOverlayClick = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (disabled || confirmed || tool !== "polygon" || draggingVertexIndex !== null) {
      return;
    }

    const point = getNormalizedPoint(event);
    markSelectionDirty();

    if (polygonClosed) {
      return;
    }

    if (points.length >= 3 && distanceBetweenPoints(point, points[0]) <= 0.03) {
      markSelectionDirty();
      setPolygonClosed(true);
      return;
    }

    markSelectionDirty();
    setPoints((current) => [...current, point]);
  };

  const handleOverlayDoubleClick = () => {
    if (disabled || confirmed || tool !== "polygon" || points.length < 3) {
      return;
    }

    markSelectionDirty();
    setPolygonClosed(true);
  };

  const handleOverlayPointerMove = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (disabled || confirmed) return;

    const point = getNormalizedPoint(event);

    if (draggingVertexIndex !== null && tool === "polygon" && polygonClosed) {
      markSelectionDirty();
      setPoints((current) =>
        current.map((currentPoint, index) =>
          index === draggingVertexIndex ? point : currentPoint,
        ),
      );
      return;
    }

    if (!isDrawing || activePointerIdRef.current !== event.pointerId) {
      return;
    }

    if (tool === "freehand") {
      setPoints((current) => {
        const lastPoint = current[current.length - 1];
        if (lastPoint && distanceBetweenPoints(lastPoint, point) < 0.004) {
          return current;
        }
        return [...current, point];
      });
      return;
    }

    if (tool === "circle") {
      setCircleDraft((current) =>
        current
          ? {
              ...current,
              current: point,
            }
          : current,
      );
    }
  };

  const finishDrawing = (pointerId: number) => {
    if (activePointerIdRef.current !== pointerId) return;

    activePointerIdRef.current = null;
    svgRef.current?.releasePointerCapture(pointerId);
    setIsDrawing(false);

    if (tool === "circle" && circleDraft) {
      const ellipsePoints = approximateEllipseAsPolygon(
        circleDraft.start,
        circleDraft.current,
      );
      setPoints(ellipsePoints);
      setPolygonClosed(true);
      setCircleDraft(null);
      return;
    }

    if (tool === "freehand") {
      setPolygonClosed(true);
    }
  };

  const handleOverlayPointerUp = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (draggingVertexIndex !== null) {
      setDraggingVertexIndex(null);
      return;
    }

    finishDrawing(event.pointerId);
  };

  const handleVertexPointerDown = (
    event: ReactPointerEvent<SVGCircleElement>,
    index: number,
  ) => {
    if (disabled || confirmed || tool !== "polygon" || !polygonClosed) return;

    event.stopPropagation();
    markSelectionDirty();
    activePointerIdRef.current = event.pointerId;
    svgRef.current?.setPointerCapture(event.pointerId);
    setDraggingVertexIndex(index);
  };

  const handleConfirm = () => {
    if (!selectionReady || imageSize.width <= 0 || imageSize.height <= 0) {
      return;
    }

    const selection = buildHealAnalyzerRoiSelection(
      tool,
      previewPoints,
      imageSize.width,
      imageSize.height,
    );
    setPoints(selection.points);
    setPolygonClosed(true);
    setCircleDraft(null);
    setConfirmed(true);
    onConfirm(selection);
  };

  const handleEdit = () => {
    if (disabled || !confirmed) return;
    setConfirmed(false);
  };

  const handleUndo = () => {
    if (disabled || confirmed || tool !== "polygon" || polygonClosed || points.length === 0) {
      return;
    }

    setPoints((current) => current.slice(0, -1));
  };

  const instruction = useMemo(() => {
    if (confirmed) {
      return "Seleção confirmada. Você pode analisar a imagem ou refazer a marcação.";
    }
    if (tool === "polygon") {
      if (polygonClosed) {
      return "Polígono fechado. Revise o contorno, arraste os pontos se precisar e confirme.";
      }
      return "Clique ao redor da ferida. Feche no primeiro ponto ou use duplo clique.";
    }
    if (tool === "freehand") {
      return "Pressione e arraste sobre a ferida em um traço contínuo, depois solte.";
    }
    return "Pressione e arraste para desenhar um círculo ou oval sobre a área da lesão.";
  }, [confirmed, polygonClosed, tool]);

  const canResetDraft = Boolean(points.length || circleDraft);

  return (
    <div className="space-y-4 select-none">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-heal-muted">
            Delimitação manual
          </p>
          <h2 className="mt-1 text-xl font-black text-heal-ink dark:text-white flex items-center gap-2 flex-wrap">
            <span>Marque a ROI na imagem</span>
            
            {/* Painel de Ações Rápidas (Paint Style) */}
            <span className="inline-flex items-center gap-1.5 ml-2">
              <button
                type="button"
                disabled={disabled || !selectionReady || confirmed}
                onClick={handleConfirm}
                className="text-heal-ink dark:text-zinc-100 hover:text-heal-blue disabled:opacity-30 transition border-0 bg-transparent p-1 cursor-pointer flex items-center justify-center rounded-lg hover:bg-heal-canvas/80 dark:hover:bg-zinc-800/60"
                title={confirmLabel}
              >
                <Save className="h-4 w-4" />
              </button>
              <span className="h-4 w-[1px] bg-heal-line dark:bg-zinc-800 mx-1" />
              <button
                type="button"
                disabled={disabled || !(tool === "polygon" && !polygonClosed && points.length > 0)}
                onClick={handleUndo}
                className="text-heal-ink dark:text-zinc-100 hover:text-heal-blue disabled:opacity-30 transition border-0 bg-transparent p-1 cursor-pointer flex items-center justify-center rounded-lg hover:bg-heal-canvas/80 dark:hover:bg-zinc-800/60"
                title="Desfazer ponto"
              >
                <Undo2 className="h-4 w-4" />
              </button>
              <button
                type="button"
                disabled={disabled || !canResetDraft}
                onClick={() => resetSelection(false)}
                className="text-heal-ink dark:text-zinc-100 hover:text-heal-blue disabled:opacity-30 transition border-0 bg-transparent p-1 cursor-pointer flex items-center justify-center rounded-lg hover:bg-heal-canvas/80 dark:hover:bg-zinc-800/60"
                title="Refazer marcação"
              >
                <Redo2 className="h-4 w-4" />
              </button>
            </span>
          </h2>
        </div>
        <RoiStatusBadge confirmed={confirmed} selectionReady={selectionReady} />
      </div>

      {/* Ferramentas e Configuração (Paint Style) */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Seletor de Formatos */}
        <div className="flex items-center gap-1">
          {TOOL_OPTIONS.map((option) => {
            const Icon = TOOL_ICONS[option.tool];
            const active = option.tool === tool;
            return (
              <button
                key={option.tool}
                type="button"
                disabled={disabled}
                onClick={() => handleToolChange(option.tool)}
                className={cn(
                  "inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-xs font-bold transition disabled:cursor-not-allowed disabled:opacity-40 border-0 cursor-pointer",
                  active
                    ? "bg-heal-blue text-white shadow-sm"
                    : "text-heal-ink dark:text-zinc-100 hover:text-heal-blue bg-transparent hover:bg-heal-canvas/80 dark:hover:bg-zinc-800/60",
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{roiToolLabel(option.tool)}</span>
              </button>
            );
          })}
        </div>

        <span className="h-4 w-[1px] bg-heal-line dark:bg-zinc-800 mx-1" />

        {/* Lápis de Edição / Borracha de Limpeza */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            disabled={disabled || !confirmed}
            onClick={handleEdit}
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-lg border-0 transition disabled:opacity-30 cursor-pointer",
              "text-heal-ink dark:text-zinc-100 hover:text-heal-blue bg-transparent hover:bg-heal-canvas/80 dark:hover:bg-zinc-800/60"
            )}
            title="Editar ROI atual"
          >
            <PencilLine className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            disabled={disabled || !canResetDraft}
            onClick={() => resetSelection(true)}
            className="flex h-8 w-8 items-center justify-center rounded-lg border-0 text-heal-ink dark:text-zinc-100 hover:text-heal-blue bg-transparent transition disabled:opacity-30 cursor-pointer hover:bg-heal-canvas/80 dark:hover:bg-zinc-800/60"
            title="Limpar marcação atual"
          >
            <Eraser className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Instrução Simples */}
      <div className="text-xs text-heal-muted dark:text-zinc-400 select-none">
        <p className="font-medium">
          <span className="font-bold text-heal-blue">{roiToolLabel(tool)}:</span> {instruction}
          {selectionReady && (
            <span className="ml-2 inline-flex items-center gap-1 rounded-full border border-heal-teal/20 bg-heal-tealSoft/50 px-2 py-0.5 text-[10px] font-black text-heal-teal">
              Área: {areaPercent}%
            </span>
          )}
        </p>
      </div>

      <div className="relative flex min-h-[350px] items-center justify-center overflow-auto rounded-2xl border border-heal-line bg-slate-950 p-3 shadow-inner sm:min-h-[400px] xl:min-h-[460px] dark:border-zinc-800">
          {/* Zoom Floating Controls */}
          <div className="absolute right-4 top-4 z-10 flex items-center gap-1 rounded-xl border border-heal-line bg-white/90 p-1 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/90 backdrop-blur-sm">
            <button
              type="button"
              onClick={() => setZoom(z => Math.max(1, z - 0.25))}
              disabled={zoom <= 1}
              className="flex h-7 w-7 items-center justify-center rounded-lg text-heal-muted hover:bg-heal-canvas hover:text-heal-ink disabled:opacity-30 dark:text-zinc-400 dark:hover:bg-zinc-800 border-0 bg-transparent cursor-pointer"
              title="Diminuir zoom"
            >
              <Minus className="h-4 w-4" />
            </button>
            <span className="text-[10px] font-bold px-1.5 min-w-[45px] text-center text-heal-ink dark:text-white select-none">
              {Math.round(zoom * 100)}%
            </span>
            <button
              type="button"
              onClick={() => setZoom(z => Math.min(3, z + 0.25))}
              disabled={zoom >= 3}
              className="flex h-7 w-7 items-center justify-center rounded-lg text-heal-muted hover:bg-heal-canvas hover:text-heal-ink disabled:opacity-30 dark:text-zinc-400 dark:hover:bg-zinc-800 border-0 bg-transparent cursor-pointer"
              title="Aumentar zoom"
            >
              <Plus className="h-4 w-4" />
            </button>
            {zoom > 1 && (
              <button
                type="button"
                onClick={() => setZoom(1)}
                className="flex h-7 w-7 items-center justify-center rounded-lg border-l border-heal-line text-heal-muted hover:bg-heal-canvas hover:text-heal-ink dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-800 pl-1 border-0 bg-transparent cursor-pointer"
                title="Resetar zoom"
              >
                <Maximize2 className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          <div
            className="relative inline-block transition-all duration-200"
            style={zoom > 1 ? {
              width: `${zoom * 100}%`,
              maxWidth: 'none',
            } : {
              maxHeight: '60vh',
              maxWidth: '100%',
            }}
          >
            <img
              ref={imgRef}
              src={imageSrc}
              alt="Imagem para delimitação manual da ferida"
              className={cn(
                "rounded-xl object-contain transition-all duration-200",
                zoom === 1 ? "max-h-[56vh] w-auto max-w-full" : "w-full h-auto"
              )}
              onLoad={(event) =>
                setImageSize({
                  width: event.currentTarget.naturalWidth,
                  height: event.currentTarget.naturalHeight,
                })
              }
            />
            <svg
              ref={svgRef}
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              className={cn(
                "absolute inset-0 h-full w-full touch-none",
                disabled ? "pointer-events-none" : "cursor-crosshair",
              )}
              onClick={handleOverlayClick}
              onDoubleClick={handleOverlayDoubleClick}
              onPointerDown={handleOverlayPointerDown}
              onPointerMove={handleOverlayPointerMove}
              onPointerUp={handleOverlayPointerUp}
            >
              <defs>
                <pattern
                  id="roi-grid"
                  width="8"
                  height="8"
                  patternUnits="userSpaceOnUse"
                >
                  <path
                    d="M 8 0 L 0 0 0 8"
                    fill="none"
                    stroke="rgba(255,255,255,0.08)"
                    strokeWidth="0.3"
                  />
                </pattern>
              </defs>
              <rect width="100" height="100" fill="url(#roi-grid)" />

              {visibleSavedSelections.map(({ selection, index }) => {
                const color =
                  SAVED_SELECTION_COLORS[index % SAVED_SELECTION_COLORS.length];
                const badgeX = toSvgCoordinate(
                  Math.max(0.02, selection.bounding_box?.x ?? 0.02),
                );
                const badgeY = toSvgCoordinate(
                  Math.max(0.05, selection.bounding_box?.y ?? 0.05),
                );

                return (
                  <g key={`saved-roi-${index}-${selection.points.length}`}>
                    <polygon
                      points={toSvgPoints(selection.points)}
                      fill={color}
                      fillOpacity="0.14"
                      stroke={color}
                      strokeWidth="1"
                      strokeLinejoin="round"
                      strokeDasharray="3 1.5"
                    />
                    <text
                      x={badgeX}
                      y={badgeY}
                      fill={color}
                      fontSize="3.2"
                      fontWeight="700"
                    >
                      ROI {index + 1}
                    </text>
                  </g>
                );
              })}

              {previewPoints.length >= 2 ? (
                <>
                  {selectionReady ? (
                    <polygon
                      points={toSvgPoints(previewPoints)}
                      fill="rgba(239,68,68,0.22)"
                      stroke={confirmed ? "#22c55e" : "#f97316"}
                      strokeWidth="1.4"
                      strokeLinejoin="round"
                    />
                  ) : (
                    <polyline
                      points={toSvgPoints(previewPoints)}
                      fill="none"
                      stroke="#f97316"
                      strokeWidth="1.4"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeDasharray="2 1.5"
                    />
                  )}
                </>
              ) : null}

              {tool === "polygon" && points.length ? (
                points.map((point, index) => (
                  <circle
                    key={`${point.x}-${point.y}-${index}`}
                    cx={toSvgCoordinate(point.x)}
                    cy={point ? toSvgCoordinate(point.y) : 0}
                    r={index === 0 && !polygonClosed ? 1.6 : 1.2}
                    fill={index === 0 && !polygonClosed ? "#fde68a" : "#ffffff"}
                    stroke="#0f172a"
                    strokeWidth="0.4"
                    className={cn(
                      !confirmed && polygonClosed ? "cursor-move" : "cursor-crosshair",
                    )}
                    onPointerDown={(event) => handleVertexPointerDown(event, index)}
                  />
                ))
              ) : null}
            </svg>
          </div>
        </div>
      </div>
  );
}

export const AnalyzerRoiEditor = WoundRoiCanvas;

function RoiStatusBadge({
  confirmed,
  selectionReady,
}: {
  confirmed: boolean;
  selectionReady: boolean;
}) {
  if (confirmed) {
    return (
      <span className="inline-flex w-fit items-center gap-2 rounded-full border border-heal-teal/20 bg-heal-tealSoft px-3 py-1.5 text-xs font-black text-heal-teal select-none">
        <CheckCircle2 className="h-3.5 w-3.5" />
        ROI salva
      </span>
    );
  }

  return (
    <span
      className={cn(
        "inline-flex w-fit items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-black select-none",
        selectionReady
          ? "border-heal-blue/20 bg-heal-softBlue text-heal-blue"
          : "border-heal-line bg-heal-canvas text-heal-muted dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400",
      )}
    >
      <PenTool className="h-3.5 w-3.5" />
      {selectionReady ? "Pronta para salvar" : "Aguardando contorno"}
    </span>
  );
}
