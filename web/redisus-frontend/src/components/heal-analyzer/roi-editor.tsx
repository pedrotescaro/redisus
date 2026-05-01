/* eslint-disable @next/next/no-img-element */
"use client";

import type { PointerEvent as ReactPointerEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2,
  Circle,
  Eraser,
  MousePointer2,
  PenTool,
  PencilLine,
  PlusCircle,
  Redo2,
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

type AnalyzerRoiEditorProps = {
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

export function AnalyzerRoiEditor({
  activeSavedSelectionIndex = null,
  confirmLabel = "Confirmar ROI",
  disabled = false,
  imageSrc,
  initialSelection = null,
  savedSelections = [],
  onConfirm,
  onSelectionCleared,
}: AnalyzerRoiEditorProps) {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const activePointerIdRef = useRef<number | null>(null);
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
    <section className="select-none overflow-hidden rounded-2xl border border-heal-line bg-white shadow-soft dark:border-zinc-800 dark:bg-zinc-900">
      <div className="border-b border-heal-line bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-heal-blue">
              Delimitação manual
            </p>
            <h2 className="mt-1 text-xl font-black text-heal-ink dark:text-white">
              Marque a ROI na imagem
            </h2>
          </div>
          <RoiStatusBadge confirmed={confirmed} selectionReady={selectionReady} />
        </div>

        <RoiToolbar
          activeTool={tool}
          confirmLabel={confirmLabel}
          disabled={disabled}
          canConfirm={!confirmed && selectionReady}
          canEdit={confirmed}
          canResetDraft={canResetDraft}
          canUndo={tool === "polygon" && !polygonClosed && points.length > 0}
          onConfirm={handleConfirm}
          onEdit={handleEdit}
          onResetDraft={() => resetSelection(false)}
          onClear={() => resetSelection(true)}
          onToolChange={handleToolChange}
          onUndo={handleUndo}
        />

        <RoiTipsCard
          areaPercent={areaPercent}
          instruction={instruction}
          selectionReady={selectionReady}
          tool={tool}
        />
      </div>

      <div className="bg-heal-canvas p-3 sm:p-4 dark:bg-zinc-950">
        <div className="flex min-h-[420px] items-center justify-center overflow-hidden rounded-2xl border border-heal-line bg-slate-950 p-3 shadow-inner sm:min-h-[520px] xl:min-h-[620px] dark:border-zinc-800">
          <div className="relative inline-block max-h-[74vh] max-w-full">
            <img
              ref={imgRef}
              src={imageSrc}
              alt="Imagem para delimitação manual da ferida"
              className="max-h-[70vh] w-auto max-w-full rounded-xl object-contain"
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
                    cy={toSvgCoordinate(point.y)}
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
    </section>
  );
}

type RoiToolbarProps = {
  activeTool: HealAnalyzerRoiTool;
  canConfirm: boolean;
  canEdit: boolean;
  canResetDraft: boolean;
  canUndo: boolean;
  confirmLabel: string;
  disabled: boolean;
  onClear: () => void;
  onConfirm: () => void;
  onEdit: () => void;
  onResetDraft: () => void;
  onToolChange: (tool: HealAnalyzerRoiTool) => void;
  onUndo: () => void;
};

function RoiToolbar({
  activeTool,
  canConfirm,
  canEdit,
  canResetDraft,
  canUndo,
  confirmLabel,
  disabled,
  onClear,
  onConfirm,
  onEdit,
  onResetDraft,
  onToolChange,
  onUndo,
}: RoiToolbarProps) {
  const actionClass =
    "inline-flex h-10 shrink-0 items-center gap-2 rounded-xl border px-3 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-40";
  const quietActionClass =
    "border-heal-line bg-white text-heal-ink hover:border-heal-blue/40 hover:bg-heal-canvas dark:border-zinc-800 dark:bg-zinc-900 dark:text-white dark:hover:bg-zinc-800";

  return (
    <div className="mt-4 space-y-2 overflow-x-auto pb-1">
      <div className="inline-flex min-w-max rounded-2xl border border-heal-line bg-heal-canvas p-1 dark:border-zinc-800 dark:bg-zinc-950">
        {TOOL_OPTIONS.map((option) => {
          const Icon = TOOL_ICONS[option.tool];
          const active = option.tool === activeTool;
          return (
            <button
              key={option.tool}
              type="button"
              disabled={disabled}
              onClick={() => onToolChange(option.tool)}
              className={cn(
                "inline-flex h-9 items-center gap-2 rounded-xl px-3 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-40",
                active
                  ? "bg-white text-heal-blue shadow-sm ring-1 ring-heal-blue/20 dark:bg-zinc-900"
                  : "text-heal-muted hover:bg-white hover:text-heal-ink dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-white",
              )}
              title={roiToolLabel(option.tool)}
            >
              <Icon className="h-4 w-4" />
              <span>{roiToolLabel(option.tool)}</span>
            </button>
          );
        })}
      </div>

      <div className="flex min-w-max gap-2 xl:min-w-0 xl:flex-wrap">
        <button
          type="button"
          className={cn(actionClass, quietActionClass)}
          disabled={disabled || !canUndo}
          onClick={onUndo}
          title="Desfazer ponto"
        >
          <Undo2 className="h-4 w-4" />
          <span>Desfazer ponto</span>
        </button>
        <button
          type="button"
          className={cn(actionClass, quietActionClass)}
          disabled={disabled || !canEdit}
          onClick={onEdit}
          title="Editar ROI atual"
        >
          <PencilLine className="h-4 w-4" />
          <span>Editar</span>
        </button>
        <button
          type="button"
          className={cn(actionClass, quietActionClass)}
          disabled={disabled || !canResetDraft}
          onClick={onResetDraft}
          title="Refazer marcação atual"
        >
          <Redo2 className="h-4 w-4" />
          <span>Refazer</span>
        </button>
        <button
          type="button"
          className={cn(actionClass, quietActionClass)}
          disabled={disabled || !canResetDraft}
          onClick={onClear}
          title="Limpar marcação atual"
        >
          <Eraser className="h-4 w-4" />
          <span>Limpar</span>
        </button>
        <button
          type="button"
          className={cn(
            actionClass,
            "border-heal-blue bg-heal-blue text-white shadow-sm hover:bg-heal-blueDark disabled:border-heal-line disabled:bg-heal-canvas disabled:text-heal-muted dark:disabled:border-zinc-800 dark:disabled:bg-zinc-950",
          )}
          disabled={disabled || !canConfirm}
          onClick={onConfirm}
          title={confirmLabel}
        >
          {confirmLabel.toLowerCase().includes("nova") ? (
            <PlusCircle className="h-4 w-4" />
          ) : (
            <CheckCircle2 className="h-4 w-4" />
          )}
          <span>{confirmLabel}</span>
        </button>
      </div>
    </div>
  );
}

function RoiTipsCard({
  areaPercent,
  instruction,
  selectionReady,
  tool,
}: {
  areaPercent: number;
  instruction: string;
  selectionReady: boolean;
  tool: HealAnalyzerRoiTool;
}) {
  return (
    <div className="mt-3 flex flex-col gap-3 rounded-2xl border border-heal-line bg-heal-canvas p-3 dark:border-zinc-800 dark:bg-zinc-950 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="text-sm font-black text-heal-ink dark:text-white">
          {roiToolLabel(tool)}: <span className="font-semibold text-heal-muted dark:text-zinc-400">{instruction}</span>
        </p>
      </div>
      {selectionReady ? (
        <span className="inline-flex shrink-0 items-center gap-2 rounded-full border border-heal-teal/20 bg-heal-tealSoft px-3 py-1.5 text-xs font-black text-heal-teal">
          <Circle className="h-3.5 w-3.5" />
          Area marcada: {areaPercent}%
        </span>
      ) : null}
    </div>
  );
}

function RoiStatusBadge({
  confirmed,
  selectionReady,
}: {
  confirmed: boolean;
  selectionReady: boolean;
}) {
  if (confirmed) {
    return (
      <span className="inline-flex w-fit items-center gap-2 rounded-full border border-heal-teal/20 bg-heal-tealSoft px-3 py-1.5 text-xs font-black text-heal-teal">
        <CheckCircle2 className="h-3.5 w-3.5" />
        ROI salva
      </span>
    );
  }

  return (
    <span
      className={cn(
        "inline-flex w-fit items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-black",
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

