/* eslint-disable @next/next/no-img-element */
"use client";

import type { PointerEvent as ReactPointerEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Circle,
  Eraser,
  Focus,
  Hand,
  Info,
  Minus,
  MousePointer2,
  PenTool,
  PencilLine,
  Plus,
  RotateCcw,
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

type PanPoint = { x: number; y: number };
type NavigationMode = "draw" | "pan";

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 4;
const ZOOM_STEP = 0.25;

const TOOL_OPTIONS: Array<{
  description: string;
  shortcut: string;
  tool: HealAnalyzerRoiTool;
}> = [
  {
    tool: "polygon",
    shortcut: "P",
    description: "Marque vértices precisos ao redor da borda da ferida.",
  },
  {
    tool: "freehand",
    shortcut: "B",
    description: "Desenhe um contorno contínuo com mouse, caneta ou toque.",
  },
  {
    tool: "circle",
    shortcut: "O",
    description: "Crie rapidamente uma seleção circular ou oval.",
  },
];

const TOOL_ICONS = {
  polygon: MousePointer2,
  freehand: PenTool,
  circle: Circle,
} satisfies Record<HealAnalyzerRoiTool, typeof MousePointer2>;

const SAVED_SELECTION_COLORS = [
  "#2dd4bf",
  "#38bdf8",
  "#fb923c",
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

function clampZoom(value: number) {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value));
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
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const activePointerIdRef = useRef<number | null>(null);
  const panStartRef = useRef<PanPoint | null>(null);
  const panOriginRef = useRef<PanPoint>({ x: 0, y: 0 });
  const ignoreNextClickRef = useRef(false);

  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<PanPoint>({ x: 0, y: 0 });
  const [navigationMode, setNavigationMode] = useState<NavigationMode>("draw");
  const [spacePressed, setSpacePressed] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const [tool, setTool] = useState<HealAnalyzerRoiTool>(
    initialSelection?.tool ?? "polygon",
  );
  const [imageSize, setImageSize] = useState({ height: 0, width: 0 });
  const [viewportSize, setViewportSize] = useState({ height: 540, width: 820 });
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
    setNavigationMode("draw");
    activePointerIdRef.current = null;
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, [imageSrc, initialSelection]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport || typeof ResizeObserver === "undefined") return undefined;

    const observer = new ResizeObserver(([entry]) => {
      if (!entry) return;
      setViewportSize({
        width: Math.max(320, entry.contentRect.width),
        height: Math.max(360, entry.contentRect.height),
      });
    });
    observer.observe(viewport);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return undefined;

    const handleViewportWheel = (event: WheelEvent) => {
      event.preventDefault();
      event.stopPropagation();

      const direction = event.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
      setZoom((current) => {
        const next = clampZoom(current + direction);
        if (next === current) return current;

        const bounds = viewport.getBoundingClientRect();
        const focusX = event.clientX - bounds.left - bounds.width / 2;
        const focusY = event.clientY - bounds.top - bounds.height / 2;
        const ratio = next / current;

        setPan((currentPan) => ({
          x: focusX - (focusX - currentPan.x) * ratio,
          y: focusY - (focusY - currentPan.y) * ratio,
        }));
        return next;
      });
    };

    viewport.addEventListener("wheel", handleViewportWheel, { passive: false });
    return () => viewport.removeEventListener("wheel", handleViewportWheel);
  }, []);

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

  const displaySize = useMemo(() => {
    if (!imageSize.width || !imageSize.height) {
      return { width: Math.max(280, viewportSize.width - 80), height: 380 };
    }

    const availableWidth = Math.max(280, viewportSize.width - 80);
    const availableHeight = Math.max(320, viewportSize.height - 56);
    const scale = Math.min(
      availableWidth / imageSize.width,
      availableHeight / imageSize.height,
      1,
    );
    return {
      width: Math.max(1, Math.round(imageSize.width * scale)),
      height: Math.max(1, Math.round(imageSize.height * scale)),
    };
  }, [imageSize, viewportSize]);

  const selectionReady =
    previewPoints.length >= 3 &&
    (tool !== "polygon" || polygonClosed || Boolean(circleDraft));
  const areaPercent = selectionReady
    ? buildHealAnalyzerRoiSelection(
        tool,
        previewPoints,
        Math.max(imageSize.width, 1),
        Math.max(imageSize.height, 1),
      ).area_ratio * 100
    : 0;
  const panEnabled = navigationMode === "pan" || spacePressed;

  const markSelectionDirty = () => setConfirmed(false);

  const resetViewport = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const changeZoom = (
    nextValue: number,
    focus?: { clientX: number; clientY: number },
  ) => {
    setZoom((current) => {
      const next = clampZoom(nextValue);
      if (next === current) return current;

      if (focus && viewportRef.current) {
        const bounds = viewportRef.current.getBoundingClientRect();
        const focusX = focus.clientX - bounds.left - bounds.width / 2;
        const focusY = focus.clientY - bounds.top - bounds.height / 2;
        const ratio = next / current;
        setPan((currentPan) => ({
          x: focusX - (focusX - currentPan.x) * ratio,
          y: focusY - (focusY - currentPan.y) * ratio,
        }));
      } else if (next <= 1) {
        setPan({ x: 0, y: 0 });
      }
      return next;
    });
  };

  const resetSelection = (notifyParent = false) => {
    setPoints([]);
    setPolygonClosed(false);
    setCircleDraft(null);
    setIsDrawing(false);
    setDraggingVertexIndex(null);
    activePointerIdRef.current = null;
    setConfirmed(false);
    if (notifyParent) onSelectionCleared();
  };

  const getNormalizedPoint = (event: ReactPointerEvent<SVGSVGElement>) => {
    const bounds = svgRef.current?.getBoundingClientRect();
    if (!bounds || bounds.width <= 0 || bounds.height <= 0) return { x: 0, y: 0 };

    return clampPoint({
      x: (event.clientX - bounds.left) / bounds.width,
      y: (event.clientY - bounds.top) / bounds.height,
    });
  };

  const handleToolChange = (nextTool: HealAnalyzerRoiTool) => {
    if (disabled) return;
    setNavigationMode("draw");
    if (nextTool === tool) return;
    setTool(nextTool);
    resetSelection(false);
  };

  const handleOverlayPointerDown = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (disabled || confirmed || panEnabled || event.button === 1) return;
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
    }
  };

  const handleOverlayClick = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (ignoreNextClickRef.current) {
      ignoreNextClickRef.current = false;
      return;
    }
    if (
      disabled ||
      confirmed ||
      panEnabled ||
      tool !== "polygon" ||
      draggingVertexIndex !== null ||
      polygonClosed
    ) {
      return;
    }

    const point = getNormalizedPoint(event);
    markSelectionDirty();
    if (points.length >= 3 && distanceBetweenPoints(point, points[0]) <= 0.025 / zoom) {
      setPolygonClosed(true);
      return;
    }
    setPoints((current) => [...current, point]);
  };

  const handleOverlayDoubleClick = () => {
    if (disabled || confirmed || panEnabled || tool !== "polygon" || points.length < 3) return;
    markSelectionDirty();
    setPolygonClosed(true);
  };

  const handleOverlayPointerMove = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (disabled || confirmed || panEnabled) return;
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

    if (!isDrawing || activePointerIdRef.current !== event.pointerId) return;
    if (tool === "freehand") {
      setPoints((current) => {
        const lastPoint = current[current.length - 1];
        if (lastPoint && distanceBetweenPoints(lastPoint, point) < 0.003 / zoom) {
          return current;
        }
        return [...current, point];
      });
      return;
    }
    if (tool === "circle") {
      setCircleDraft((current) => (current ? { ...current, current: point } : current));
    }
  };

  const finishDrawing = (pointerId: number) => {
    if (activePointerIdRef.current !== pointerId) return;
    activePointerIdRef.current = null;
    if (svgRef.current?.hasPointerCapture(pointerId)) {
      svgRef.current.releasePointerCapture(pointerId);
    }
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
    if (tool === "freehand") setPolygonClosed(true);
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
    if (disabled || confirmed || panEnabled || tool !== "polygon" || !polygonClosed) return;
    event.stopPropagation();
    markSelectionDirty();
    activePointerIdRef.current = event.pointerId;
    svgRef.current?.setPointerCapture(event.pointerId);
    setDraggingVertexIndex(index);
  };

  const handleConfirm = () => {
    if (!selectionReady || imageSize.width <= 0 || imageSize.height <= 0) return;
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
    setNavigationMode("draw");
    setConfirmed(false);
  };

  const handleUndo = () => {
    if (disabled || confirmed) return;
    if (tool === "polygon" && points.length) {
      if (polygonClosed) setPolygonClosed(false);
      else setPoints((current) => current.slice(0, -1));
      return;
    }
    resetSelection(false);
  };

  const handleViewportPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (disabled || (!panEnabled && event.button !== 1)) return;

    const target = event.target as Element | null;
    if (target?.closest("button, input, select, textarea, a, [role='button']")) {
      return;
    }

    event.preventDefault();
    viewportRef.current?.setPointerCapture(event.pointerId);
    panStartRef.current = { x: event.clientX, y: event.clientY };
    panOriginRef.current = pan;
    ignoreNextClickRef.current = true;
    setIsPanning(true);
  };

  const handleViewportPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!isPanning || !panStartRef.current) return;
    setPan({
      x: panOriginRef.current.x + event.clientX - panStartRef.current.x,
      y: panOriginRef.current.y + event.clientY - panStartRef.current.y,
    });
  };

  const endPanning = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!isPanning) return;
    if (viewportRef.current?.hasPointerCapture(event.pointerId)) {
      viewportRef.current.releasePointerCapture(event.pointerId);
    }
    panStartRef.current = null;
    setIsPanning(false);
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.matches("input, textarea, select, [contenteditable='true']")) return;

      if (event.code === "Space") {
        event.preventDefault();
        setSpacePressed(true);
      } else if (event.key.toLowerCase() === "p") {
        handleToolChange("polygon");
      } else if (event.key.toLowerCase() === "b") {
        handleToolChange("freehand");
      } else if (event.key.toLowerCase() === "o") {
        handleToolChange("circle");
      } else if (event.key === "0") {
        resetViewport();
      } else if (event.key === "+" || event.key === "=") {
        changeZoom(zoom + ZOOM_STEP);
      } else if (event.key === "-") {
        changeZoom(zoom - ZOOM_STEP);
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        handleUndo();
      } else if (event.key === "Escape" && (points.length || circleDraft)) {
        resetSelection(false);
      }
    };
    const onKeyUp = (event: KeyboardEvent) => {
      if (event.code === "Space") setSpacePressed(false);
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  });

  const instruction = useMemo(() => {
    if (panEnabled) return "Arraste para navegar. Solte Espaço para voltar ao contorno.";
    if (confirmed) return "ROI salva. Edite o contorno ou inicie a análise.";
    if (tool === "polygon" && polygonClosed) {
      return "Contorno fechado. Arraste os vértices para refinar e depois salve.";
    }
    if (tool === "polygon") return "Clique na borda da ferida; feche no ponto inicial ou com duplo clique.";
    if (tool === "freehand") return "Pressione e contorne a ferida em um único traço.";
    return "Pressione e arraste de uma extremidade à outra da ferida.";
  }, [confirmed, panEnabled, polygonClosed, tool]);

  const canResetDraft = Boolean(points.length || circleDraft);

  return (
    <div className="overflow-hidden rounded-[26px] border border-slate-800 bg-[#0d1117] shadow-[0_24px_60px_rgba(15,23,42,0.18)]">
      <div className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-[#161b22] px-3 py-2 text-white sm:px-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-cyan-400/10 text-cyan-300 ring-1 ring-cyan-300/20">
            <Focus className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-black">ROI Studio</p>
            <p className="truncate text-[10px] font-medium text-slate-400">
              Contorno manual normalizado • {imageSize.width || "—"} × {imageSize.height || "—"} px
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleUndo}
            disabled={disabled || confirmed || !canResetDraft}
            className="flex h-8 w-8 items-center justify-center rounded-lg border-0 bg-transparent text-slate-300 transition hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
            title="Desfazer (Ctrl+Z)"
          >
            <Undo2 className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => resetSelection(false)}
            disabled={disabled || !canResetDraft}
            className="flex h-8 w-8 items-center justify-center rounded-lg border-0 bg-transparent text-slate-300 transition hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
            title="Recomeçar contorno"
          >
            <RotateCcw className="h-4 w-4" />
          </button>
          <span className="mx-1 h-5 w-px bg-white/10" />
          {confirmed ? (
            <button
              type="button"
              onClick={handleEdit}
              disabled={disabled}
              className="inline-flex h-8 items-center gap-2 rounded-lg bg-white/10 px-3 text-xs font-bold text-white transition hover:bg-white/15 disabled:opacity-40"
            >
              <PencilLine className="h-3.5 w-3.5" />
              Editar
            </button>
          ) : (
            <button
              type="button"
              onClick={handleConfirm}
              disabled={disabled || !selectionReady}
              className="inline-flex h-8 items-center gap-2 rounded-lg bg-cyan-400 px-3 text-xs font-black text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-35"
            >
              <Save className="h-3.5 w-3.5" />
              {confirmLabel}
            </button>
          )}
        </div>
      </div>

      <div
        ref={viewportRef}
        data-testid="wound-roi-viewport"
        className={cn(
          "relative h-[460px] touch-none overscroll-none overflow-hidden sm:h-[540px] xl:h-[min(64vh,720px)]",
          panEnabled ? (isPanning ? "cursor-grabbing" : "cursor-grab") : "cursor-crosshair",
        )}
        style={{
          backgroundColor: "#090d12",
          backgroundImage:
            "linear-gradient(45deg, rgba(255,255,255,.025) 25%, transparent 25%), linear-gradient(-45deg, rgba(255,255,255,.025) 25%, transparent 25%), linear-gradient(45deg, transparent 75%, rgba(255,255,255,.025) 75%), linear-gradient(-45deg, transparent 75%, rgba(255,255,255,.025) 75%)",
          backgroundPosition: "0 0, 0 8px, 8px -8px, -8px 0px",
          backgroundSize: "16px 16px",
        }}
        onPointerDown={handleViewportPointerDown}
        onPointerMove={handleViewportPointerMove}
        onPointerUp={endPanning}
        onPointerCancel={endPanning}
      >
        <div className="absolute left-3 top-1/2 z-20 flex -translate-y-1/2 flex-col gap-1 rounded-2xl border border-white/10 bg-[#161b22]/95 p-1.5 shadow-2xl backdrop-blur">
          <EditorToolButton
            active={navigationMode === "pan"}
            icon={<Hand className="h-4 w-4" />}
            label="Mover canvas"
            shortcut="Espaço"
            onClick={() => setNavigationMode((current) => (current === "pan" ? "draw" : "pan"))}
          />
          <span className="mx-auto my-1 h-px w-7 bg-white/10" />
          {TOOL_OPTIONS.map((option) => {
            const Icon = TOOL_ICONS[option.tool];
            return (
              <EditorToolButton
                key={option.tool}
                active={navigationMode === "draw" && option.tool === tool}
                description={option.description}
                disabled={disabled}
                icon={<Icon className="h-4 w-4" />}
                label={roiToolLabel(option.tool)}
                shortcut={option.shortcut}
                onClick={() => handleToolChange(option.tool)}
              />
            );
          })}
          <span className="mx-auto my-1 h-px w-7 bg-white/10" />
          <EditorToolButton
            disabled={disabled || !canResetDraft}
            icon={<Eraser className="h-4 w-4" />}
            label="Limpar contorno atual"
            shortcut="Esc"
            onClick={() => resetSelection(true)}
          />
        </div>

        <div className="absolute right-3 top-3 z-20 flex items-center gap-1 rounded-xl border border-white/10 bg-[#161b22]/95 p-1 text-white shadow-xl backdrop-blur">
          <button
            type="button"
            onClick={() => changeZoom(zoom - ZOOM_STEP)}
            disabled={zoom <= MIN_ZOOM}
            className="flex h-8 w-8 items-center justify-center rounded-lg border-0 bg-transparent text-slate-300 transition hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
            title="Diminuir zoom (-)"
          >
            <Minus className="h-4 w-4" />
          </button>
          <span className="min-w-14 text-center text-[11px] font-black tabular-nums">
            {Math.round(zoom * 100)}%
          </span>
          <button
            type="button"
            onClick={() => changeZoom(zoom + ZOOM_STEP)}
            disabled={zoom >= MAX_ZOOM}
            className="flex h-8 w-8 items-center justify-center rounded-lg border-0 bg-transparent text-slate-300 transition hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
            title="Aumentar zoom (+)"
          >
            <Plus className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={resetViewport}
            className="flex h-8 w-8 items-center justify-center rounded-lg border-0 bg-transparent text-slate-300 transition hover:bg-white/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
            title="Ajustar à tela (0)"
          >
            <Focus className="h-4 w-4" />
          </button>
        </div>

        <div
          className="absolute left-1/2 top-1/2 will-change-transform"
          style={{
            width: `${displaySize.width}px`,
            height: `${displaySize.height}px`,
            transform: `translate(-50%, -50%) translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "center center",
          }}
        >
          <div className="relative h-full w-full overflow-hidden rounded-md bg-black shadow-[0_28px_80px_rgba(0,0,0,.5)] ring-1 ring-white/15">
            <img
              src={imageSrc}
              alt="Imagem clínica para delimitação manual da ferida"
              draggable={false}
              className="block h-full w-full select-none object-fill"
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
                disabled ? "pointer-events-none" : panEnabled ? "cursor-grab" : "cursor-crosshair",
              )}
              onClick={handleOverlayClick}
              onDoubleClick={handleOverlayDoubleClick}
              onPointerDown={handleOverlayPointerDown}
              onPointerMove={handleOverlayPointerMove}
              onPointerUp={handleOverlayPointerUp}
              onPointerCancel={handleOverlayPointerUp}
            >
              <defs>
                <pattern id="roi-grid" width="10" height="10" patternUnits="userSpaceOnUse">
                  <path d="M 10 0 L 0 0 0 10" fill="none" stroke="rgba(255,255,255,.13)" strokeWidth="0.18" />
                </pattern>
                <filter id="roi-glow">
                  <feGaussianBlur stdDeviation="0.5" result="coloredBlur" />
                  <feMerge>
                    <feMergeNode in="coloredBlur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>
              <rect width="100" height="100" fill="url(#roi-grid)" pointerEvents="none" />

              {visibleSavedSelections.map(({ selection, index }) => {
                const color = SAVED_SELECTION_COLORS[index % SAVED_SELECTION_COLORS.length];
                const badgeX = toSvgCoordinate(Math.max(0.025, selection.bounding_box?.x ?? 0.025));
                const badgeY = toSvgCoordinate(Math.max(0.065, selection.bounding_box?.y ?? 0.065));
                return (
                  <g key={`saved-roi-${index}-${selection.points.length}`} pointerEvents="none">
                    <polygon
                      points={toSvgPoints(selection.points)}
                      fill={color}
                      fillOpacity="0.16"
                      stroke={color}
                      strokeWidth={0.8 / zoom}
                      vectorEffect="non-scaling-stroke"
                      strokeLinejoin="round"
                      strokeDasharray="5 3"
                    />
                    <text x={badgeX} y={badgeY} fill={color} fontSize={3 / zoom} fontWeight="800">
                      ROI {index + 1}
                    </text>
                  </g>
                );
              })}

              {previewPoints.length >= 2 ? (
                selectionReady ? (
                  <polygon
                    points={toSvgPoints(previewPoints)}
                    fill="rgba(6,182,212,.2)"
                    stroke={confirmed ? "#2dd4bf" : "#22d3ee"}
                    strokeWidth={1.6 / zoom}
                    vectorEffect="non-scaling-stroke"
                    strokeLinejoin="round"
                    filter="url(#roi-glow)"
                  />
                ) : (
                  <polyline
                    points={toSvgPoints(previewPoints)}
                    fill="none"
                    stroke="#22d3ee"
                    strokeWidth={1.6 / zoom}
                    vectorEffect="non-scaling-stroke"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeDasharray="5 3"
                  />
                )
              ) : null}

              {tool === "polygon" && points.length
                ? points.map((point, index) => (
                    <circle
                      key={`${point.x}-${point.y}-${index}`}
                      cx={toSvgCoordinate(point.x)}
                      cy={toSvgCoordinate(point.y)}
                      r={(index === 0 && !polygonClosed ? 1.8 : 1.3) / zoom}
                      fill={index === 0 && !polygonClosed ? "#fef08a" : "#ecfeff"}
                      stroke="#083344"
                      strokeWidth={0.55 / zoom}
                      className={cn(!confirmed && polygonClosed ? "cursor-move" : "cursor-crosshair")}
                      onPointerDown={(event) => handleVertexPointerDown(event, index)}
                    />
                  ))
                : null}
            </svg>
          </div>
        </div>

        <div className="pointer-events-none absolute bottom-3 left-1/2 z-20 flex max-w-[calc(100%-7rem)] -translate-x-1/2 items-center gap-2 rounded-full border border-white/10 bg-[#161b22]/90 px-3 py-2 text-[11px] font-semibold text-slate-200 shadow-xl backdrop-blur">
          <Info className="h-3.5 w-3.5 shrink-0 text-cyan-300" />
          <span className="truncate">{instruction}</span>
        </div>
      </div>

      <div className="flex min-h-10 flex-wrap items-center justify-between gap-2 border-t border-white/10 bg-[#161b22] px-4 py-2 text-[10px] font-semibold text-slate-400">
        <div className="flex items-center gap-3">
          <span className="text-slate-200">{roiToolLabel(tool)}</span>
          <span>{points.length} pontos</span>
          <span>{selectionReady ? `${areaPercent.toFixed(areaPercent < 1 ? 2 : 1)}% da imagem` : "Área pendente"}</span>
        </div>
        <div className="hidden items-center gap-3 sm:flex">
          <span>Scroll: zoom</span>
          <span>Espaço + arrastar: mover</span>
          <span>0: ajustar</span>
        </div>
      </div>
    </div>
  );
}

function EditorToolButton({
  active = false,
  description,
  disabled = false,
  icon,
  label,
  onClick,
  shortcut,
}: {
  active?: boolean;
  description?: string;
  disabled?: boolean;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  shortcut: string;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={active}
      disabled={disabled}
      onClick={onClick}
      title={`${label}${description ? `: ${description}` : ""} (${shortcut})`}
      className={cn(
        "group relative flex h-9 w-9 items-center justify-center rounded-xl border text-slate-300 transition disabled:cursor-not-allowed disabled:opacity-30",
        active
          ? "border-cyan-300/30 bg-cyan-400 text-slate-950 shadow-[0_0_24px_rgba(34,211,238,.2)]"
          : "border-transparent bg-transparent hover:border-white/10 hover:bg-white/10 hover:text-white",
      )}
    >
      {icon}
      <span className="pointer-events-none absolute left-12 z-30 hidden whitespace-nowrap rounded-lg border border-white/10 bg-[#161b22] px-2.5 py-1.5 text-[10px] font-bold text-white shadow-xl group-hover:block">
        {label} · {shortcut}
      </span>
    </button>
  );
}

export const AnalyzerRoiEditor = WoundRoiCanvas;
