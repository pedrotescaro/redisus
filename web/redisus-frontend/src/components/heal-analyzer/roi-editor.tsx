/* eslint-disable @next/next/no-img-element */
"use client";

import type { PointerEvent as ReactPointerEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2,
  Circle,
  PenTool,
  RefreshCcw,
  Trash2,
  Undo2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  approximateEllipseAsPolygon,
  buildHealAnalyzerRoiSelection,
  clampPoint,
  distanceBetweenPoints,
  roiToolLabel,
  type HealAnalyzerRoiPoint,
  type HealAnalyzerRoiSelection,
  type HealAnalyzerRoiTool,
} from "@/lib/heal-analyzer-roi";
import { cn } from "@/lib/utils";

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
    description: "Desenhe a area da lesao em um traco continuo.",
  },
  {
    tool: "circle",
    description: "Arraste para criar um circulo/ovalo rapido sobre a ferida.",
  },
];

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
      return "Selecao confirmada. Voce pode analisar a imagem ou refazer a marcacao.";
    }
    if (tool === "polygon") {
      if (polygonClosed) {
        return "Poligono fechado. Revise o contorno, arraste os pontos se precisar e confirme.";
      }
      return "Clique ao redor da ferida. Feche no primeiro ponto ou use duplo clique.";
    }
    if (tool === "freehand") {
      return "Pressione e arraste sobre a ferida em um traco continuo, depois solte.";
    }
    return "Pressione e arraste para desenhar um circulo ou oval sobre a area da lesao.";
  }, [confirmed, polygonClosed, tool]);

  return (
    <section className="rounded-[28px] border border-outline-variant/20 bg-surface-container-lowest/85 p-5 shadow-ambient dark:border-white/10 dark:bg-surface-container-lowest/70">
      <div className="flex flex-col gap-4 border-b border-outline-variant/15 pb-4 dark:border-white/10">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-primary">
              Delimitacao manual
            </p>
            <h2 className="mt-2 text-2xl font-extrabold text-on-surface">
              Marque exatamente onde estao as feridas
            </h2>
            <p className="mt-2 text-sm text-on-surface-variant">
              Adicione uma ou mais ROIs manuais antes de rodar a analise. A pipeline
              clinica vai usar somente as regioes confirmadas como filtro principal
              para segmentacao, tecidos e leitura visual.
            </p>
          </div>

          <div className="inline-flex max-w-fit items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-300">
            <CheckCircle2 className="h-3.5 w-3.5" />
            {confirmed ? "ROI confirmada" : "Analise bloqueada ate confirmar"}
          </div>
        </div>

        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-wrap gap-2">
            {TOOL_OPTIONS.map((option) => (
              <button
                key={option.tool}
                type="button"
                disabled={disabled}
                onClick={() => handleToolChange(option.tool)}
                className={cn(
                  "rounded-full border px-4 py-2 text-sm transition-all disabled:cursor-not-allowed disabled:opacity-50",
                  option.tool === tool
                    ? "border-primary/30 bg-primary/10 text-primary dark:border-primary/40 dark:bg-primary/15"
                    : "border-outline-variant/20 bg-surface-container-high text-on-surface-variant hover:border-primary/25 hover:text-on-surface dark:border-white/10 dark:bg-white/5",
                )}
              >
                {roiToolLabel(option.tool)}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={handleUndo}
              disabled={disabled || tool !== "polygon" || polygonClosed || points.length === 0}
            >
              <Undo2 className="h-4 w-4" />
              Desfazer ponto
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={handleEdit}
              disabled={disabled || !confirmed}
            >
              <PenTool className="h-4 w-4" />
              Editar
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => resetSelection(false)}
              disabled={disabled || (!points.length && !circleDraft)}
            >
              <RefreshCcw className="h-4 w-4" />
              Refazer
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => resetSelection(true)}
              disabled={disabled || (!points.length && !circleDraft)}
            >
              <Trash2 className="h-4 w-4" />
              Limpar
            </Button>
            <Button
              type="button"
              onClick={handleConfirm}
              disabled={disabled || confirmed || !selectionReady}
            >
              <CheckCircle2 className="h-4 w-4" />
              {confirmLabel}
            </Button>
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_260px]">
        <div className="rounded-[24px] border border-outline-variant/20 bg-[linear-gradient(180deg,#f8fbff_0%,#eef3fa_100%)] p-4 dark:border-white/10 dark:bg-[linear-gradient(180deg,#0b1322_0%,#08111f_100%)]">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-lg font-bold text-slate-900 dark:text-white">
                Ferramenta ativa: {roiToolLabel(tool)}
              </p>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                {TOOL_OPTIONS.find((option) => option.tool === tool)?.description}
              </p>
            </div>
            {selectionReady ? (
              <div className="rounded-full border border-outline-variant/20 bg-surface-container px-3 py-2 text-xs font-semibold text-on-surface dark:border-white/10 dark:bg-white/5">
                Area marcada: {areaPercent}%
              </div>
            ) : null}
          </div>

          <div className="flex justify-center overflow-hidden rounded-[20px] border border-primary/10 bg-black/90 p-3">
            <div className="relative inline-block max-h-[72vh] max-w-full">
              <img
                ref={imgRef}
                src={imageSrc}
                alt="Imagem para delimitacao manual da ferida"
                className="max-h-[68vh] w-auto max-w-full rounded-[16px] object-contain"
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

        <div className="space-y-5">
          <div className="rounded-[24px] border border-outline-variant/20 bg-surface-container p-4 dark:border-white/10">
            <p className="text-sm font-semibold text-on-surface">Guia rapido</p>
            <p className="mt-2 text-sm leading-7 text-on-surface-variant">
              {instruction}
            </p>
          </div>

          <div className="rounded-[24px] border border-outline-variant/20 bg-surface-container p-4 dark:border-white/10">
            <p className="text-sm font-semibold text-on-surface">Sugestao de uso</p>
            <ul className="mt-3 space-y-3 text-sm text-on-surface-variant">
              <li className="rounded-2xl border border-outline-variant/20 bg-surface-container-high px-3 py-3 dark:border-white/10 dark:bg-white/5">
                Use poligono quando quiser contornar bordas irregulares com mais precisao.
              </li>
              <li className="rounded-2xl border border-outline-variant/20 bg-surface-container-high px-3 py-3 dark:border-white/10 dark:bg-white/5">
                O desenho livre e mais rapido para lesoes extensas, mas vale revisar o traco antes de confirmar.
              </li>
              <li className="rounded-2xl border border-outline-variant/20 bg-surface-container-high px-3 py-3 dark:border-white/10 dark:bg-white/5">
                Se a borda da ferida estiver muito difusa, prefira cobrir somente o leito principal e deixar pele sadia de fora.
              </li>
            </ul>
          </div>

          <div className="rounded-[24px] border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-500/20 dark:bg-emerald-500/10">
            <div className="flex items-center gap-2 text-emerald-800 dark:text-emerald-100">
              <Circle className="h-4 w-4" />
              <p className="text-sm font-semibold">Estado atual</p>
            </div>
            <p className="mt-2 text-sm leading-7 text-emerald-900 dark:text-emerald-50/90">
              {confirmed
                ? `ROI confirmada com a ferramenta ${roiToolLabel(tool).toLowerCase()}.`
                : selectionReady
                  ? "A marcacao esta pronta para ser salva. Revise o contorno e adicione a ROI a lista confirmada."
                  : "Aguardando uma marcacao valida de uma ferida para adicionar a ROI."}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
