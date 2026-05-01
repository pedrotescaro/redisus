/* eslint-disable @next/next/no-img-element */
"use client";

import type { ChangeEvent, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import {
  BadgeCheck,
  CheckCircle2,
  FileImage,
  ImagePlus,
  LoaderCircle,
  Plus,
  RefreshCcw,
  ScanSearch,
  ShieldAlert,
  Trash2,
  X,
} from "lucide-react";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { AnalyzerRoiEditor } from "./roi-editor";
import { AnalysisResultPanel } from "./analyzer-summary";
import { AnalyzerTechnicalDrawer } from "./analyzer-technical-drawer";
import { AnalyzerViewer } from "./analyzer-viewer";
import {
  getStatusCopy,
  getTissueBreakdown,
  type AnalyzerTabId,
  type WorkflowState,
} from "./presenter";
import {
  isHealAnalyzerRoiSelection,
  roiToolLabel,
  type HealAnalyzerRoiSelection,
} from "../../lib/heal-analyzer-roi";
import { cn } from "../../lib/utils";
import {
  analyzeWithHealAnalyzer,
  type HealAnalyzerResult,
} from "../../services/ai/heal-analyzer-service";

type MobilePanel = "image" | "roi" | "result";

const captureTips = [
  "Evite sombras fortes e reflexos sobre o leito.",
  "Aproxime a camera o suficiente para mostrar textura e cor.",
  "Use uma ROI por ferida quando houver mais de uma lesao.",
] as const;

function getNextVisualTab(result: HealAnalyzerResult): AnalyzerTabId {
  if (result.visuals?.combined?.data_url) return "combined";
  if (result.visuals?.segmentation?.data_url) return "segmentation";
  if (result.visuals?.attention?.data_url) return "attention";
  return "original";
}

function getResultRoiSelections(result: HealAnalyzerResult) {
  if (result.rois?.length) {
    return result.rois.filter(isHealAnalyzerRoiSelection);
  }

  if (isHealAnalyzerRoiSelection(result.roi)) {
    return [result.roi];
  }

  return [];
}

function getRoiCountLabel(count: number) {
  if (count === 0) return "Nenhuma ROI criada";
  if (count === 1) return "1 ROI criada";
  return `${count} ROIs criadas`;
}

export function AnalyzerWorkbench() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const roiFeedbackTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [activeMobilePanel, setActiveMobilePanel] = useState<MobilePanel>("image");
  const [analysis, setAnalysis] = useState<HealAnalyzerResult | null>(null);
  const [activeTab, setActiveTab] = useState<AnalyzerTabId>("original");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lightbox, setLightbox] = useState<{ label: string; src: string } | null>(
    null,
  );
  const [patientId, setPatientId] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [editingRoiIndex, setEditingRoiIndex] = useState<number | null>(null);
  const [roiFeedback, setRoiFeedback] = useState<string | null>(null);
  const [roiSelections, setRoiSelections] = useState<HealAnalyzerRoiSelection[]>([]);
  const [roiEditorKey, setRoiEditorKey] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [workflowState, setWorkflowState] = useState<WorkflowState>("idle");

  useEffect(() => {
    return () => {
      if (previewUrl?.startsWith("blob:")) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  useEffect(() => {
    return () => {
      if (roiFeedbackTimeoutRef.current) {
        clearTimeout(roiFeedbackTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!drawerOpen && !lightbox) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (lightbox) {
        setLightbox(null);
        return;
      }
      setDrawerOpen(false);
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [drawerOpen, lightbox]);

  const loading = workflowState === "loading";
  const hasImage = Boolean(previewUrl);
  const hasConfirmedRoi = roiSelections.length > 0;
  const activeEditorSelection =
    editingRoiIndex !== null ? roiSelections[editingRoiIndex] ?? null : null;
  const status = getStatusCopy(workflowState, hasImage, hasConfirmedRoi);
  const tissueLegend = getTissueBreakdown(analysis).slice(0, 4);

  const viewerTabs = [
    {
      id: "original" as const,
      label: "Original",
      description: "Foto enviada antes de qualquer processamento.",
      src: previewUrl,
    },
    {
      id: "segmentation" as const,
      label: "Segmentacao",
      description: "Mapa de tecidos identificado pelo pipeline clinico.",
      src: analysis?.visuals?.segmentation?.data_url ?? null,
    },
    {
      id: "combined" as const,
      label: "Combinada",
      description: "Foto original combinada com a leitura visual da IA.",
      src: analysis?.visuals?.combined?.data_url ?? null,
    },
    {
      id: "attention" as const,
      label: "Atencao da IA",
      description: "Regioes de maior relevancia para a decisao do modelo.",
      src: analysis?.visuals?.attention?.data_url ?? null,
    },
  ];

  const showRoiFeedback = (message: string) => {
    setRoiFeedback(message);
    if (roiFeedbackTimeoutRef.current) {
      clearTimeout(roiFeedbackTimeoutRef.current);
    }
    roiFeedbackTimeoutRef.current = setTimeout(() => setRoiFeedback(null), 2600);
  };

  const handleSelectImage = () => {
    fileInputRef.current?.click();
  };

  const resetAnalysisPreview = () => {
    setAnalysis(null);
    setError(null);
    setActiveTab("original");
    setDrawerOpen(false);
  };

  const handleRoiCleared = () => {
    resetAnalysisPreview();
    setEditingRoiIndex(null);
    setRoiEditorKey((current) => current + 1);
    setWorkflowState(previewUrl ? (roiSelections.length ? "ready" : "marking") : "idle");
  };

  const handleRoiConfirmed = (selection: HealAnalyzerRoiSelection) => {
    const nextLabel =
      editingRoiIndex === null ? `ROI ${roiSelections.length + 1}` : `ROI ${editingRoiIndex + 1}`;
    resetAnalysisPreview();
    setEditingRoiIndex(null);
    setRoiSelections((current) => {
      if (editingRoiIndex === null) {
        return [...current, selection];
      }

      return current.map((currentSelection, index) =>
        index === editingRoiIndex ? selection : currentSelection,
      );
    });
    setRoiEditorKey((current) => current + 1);
    setWorkflowState("ready");
    setActiveMobilePanel("roi");
    showRoiFeedback(`${nextLabel} salva com sucesso.`);
  };

  const handleResetRoi = () => {
    if (
      roiSelections.length &&
      !window.confirm("Limpar todas as ROIs marcadas? Essa acao remove as delimitacoes salvas nesta analise.")
    ) {
      return;
    }

    resetAnalysisPreview();
    setError(null);
    setEditingRoiIndex(null);
    setRoiSelections([]);
    setWorkflowState(previewUrl ? "marking" : "idle");
    setRoiEditorKey((current) => current + 1);
    setRoiFeedback(null);
  };

  const handleStartNewRoi = () => {
    resetAnalysisPreview();
    setEditingRoiIndex(null);
    setError(null);
    setRoiEditorKey((current) => current + 1);
    setWorkflowState(previewUrl ? (roiSelections.length ? "ready" : "marking") : "idle");
    setActiveMobilePanel("roi");
  };

  const handleEditSavedRoi = (index: number) => {
    if (!roiSelections[index]) return;
    resetAnalysisPreview();
    setError(null);
    setEditingRoiIndex(index);
    setRoiEditorKey((current) => current + 1);
    setWorkflowState("ready");
    setActiveMobilePanel("roi");
  };

  const handleRemoveSavedRoi = (index: number) => {
    resetAnalysisPreview();
    let remainingSelections = 0;
    setRoiSelections((current) => {
      const nextSelections = current.filter((_, currentIndex) => currentIndex !== index);
      remainingSelections = nextSelections.length;
      return nextSelections;
    });
    setEditingRoiIndex((current) => {
      if (current === null) return null;
      if (current === index) return null;
      if (current > index) return current - 1;
      return current;
    });
    setRoiEditorKey((current) => current + 1);
    setWorkflowState(previewUrl ? (remainingSelections > 0 ? "ready" : "marking") : "idle");
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.currentTarget.value = "";
    if (!file) return;

    const nextPreview = URL.createObjectURL(file);

    setSelectedFile(file);
    setPreviewUrl(nextPreview);
    setEditingRoiIndex(null);
    setRoiSelections([]);
    resetAnalysisPreview();
    setRoiEditorKey((current) => current + 1);
    setWorkflowState("marking");
    setActiveMobilePanel("roi");
    setRoiFeedback(null);
  };

  const handleAnalyze = async () => {
    if (!selectedFile) return;

    if (!roiSelections.length) {
      setError("Confirme pelo menos uma area marcada da ferida antes de iniciar a analise.");
      setWorkflowState("marking");
      setActiveMobilePanel("roi");
      return;
    }

    setWorkflowState("loading");
    setError(null);
    setActiveMobilePanel("result");

    try {
      const result = await analyzeWithHealAnalyzer(selectedFile, {
        patientId,
        roiSelections,
      });
      setAnalysis(result);
      setEditingRoiIndex(null);
      setRoiSelections(getResultRoiSelections(result));
      setWorkflowState("complete");
      setActiveTab(getNextVisualTab(result));
      setActiveMobilePanel("result");
    } catch (analysisError) {
      const message =
        analysisError instanceof Error
          ? analysisError.message
          : "Falha ao executar a analise da imagem.";
      setError(message);
      setWorkflowState("error");
      setActiveMobilePanel("result");
    }
  };

  return (
    <>
      <section className="space-y-5">
        <div className="rounded-2xl border border-heal-line bg-white p-5 shadow-soft dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-heal-blue">
                HEAL analyzer
              </p>
              <h1 className="mt-2 text-2xl font-black text-heal-ink dark:text-white sm:text-3xl">
                Analise de imagem com ROI manual
              </h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-heal-muted dark:text-zinc-400">
                Escolha a imagem, delimite uma ou mais regioes da ferida e execute a IA
                usando somente as areas confirmadas.
              </p>
            </div>
            <div
              className={`inline-flex w-fit items-center gap-2 rounded-full border px-3 py-2 text-sm font-bold ${status.tone}`}
            >
              {loading ? (
                <LoaderCircle className="h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle2 className="h-4 w-4" />
              )}
              <span>{status.label}</span>
            </div>
          </div>
        </div>

        <MobileAnalyzerTabs
          activePanel={activeMobilePanel}
          roiCount={roiSelections.length}
          onChange={setActiveMobilePanel}
        />

        <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)] xl:grid-cols-[300px_minmax(0,1fr)_360px]">
          <ImageInfoPanel
            className={cn(activeMobilePanel === "image" ? "block" : "hidden lg:block")}
            fileInputRef={fileInputRef}
            hasConfirmedRoi={hasConfirmedRoi}
            loading={loading}
            onAnalyze={() => void handleAnalyze()}
            onFileChange={handleFileChange}
            onResetRoi={handleResetRoi}
            onSelectImage={handleSelectImage}
            patientId={patientId}
            previewUrl={previewUrl}
            roiCount={roiSelections.length}
            selectedFile={selectedFile}
            setPatientId={setPatientId}
          />

          <div className={cn(activeMobilePanel === "roi" ? "block" : "hidden lg:block")}>
            <RoiCanvasPanel
              editingRoiIndex={editingRoiIndex}
              hasImage={hasImage}
              onEditRoi={handleEditSavedRoi}
              onNewRoi={handleStartNewRoi}
              onRemoveRoi={handleRemoveSavedRoi}
              roiFeedback={roiFeedback}
              roiSelections={roiSelections}
            >
              {analysis ? (
                <AnalyzerViewer
                  activeTab={activeTab}
                  detectionImage={analysis?.visuals?.detection?.data_url ?? null}
                  loading={loading}
                  onOpenLightbox={(src, label) => setLightbox({ src, label })}
                  onTabChange={setActiveTab}
                  tabs={viewerTabs}
                  tissueLegend={tissueLegend}
                />
              ) : hasImage && previewUrl ? (
                <AnalyzerRoiEditor
                  key={`${previewUrl}-${roiEditorKey}-${editingRoiIndex ?? "new"}`}
                  activeSavedSelectionIndex={editingRoiIndex}
                  confirmLabel={
                    editingRoiIndex !== null
                      ? `Atualizar ROI ${editingRoiIndex + 1}`
                      : hasConfirmedRoi
                        ? "Salvar nova ROI"
                        : "Salvar primeira ROI"
                  }
                  disabled={loading}
                  imageSrc={previewUrl}
                  initialSelection={activeEditorSelection}
                  savedSelections={roiSelections}
                  onConfirm={handleRoiConfirmed}
                  onSelectionCleared={handleRoiCleared}
                />
              ) : (
                <EmptyCanvasPanel />
              )}
            </RoiCanvasPanel>
          </div>

          <div
            className={cn(
              activeMobilePanel === "result" ? "block" : "hidden lg:block",
              "lg:col-span-2 xl:col-span-1",
            )}
          >
            <AnalysisResultPanel
              analysis={analysis}
              error={error}
              hasConfirmedRoi={hasConfirmedRoi}
              hasImage={hasImage}
              loading={loading}
              onOpenTechnical={() => setDrawerOpen(true)}
              onRunAnalysis={() => void handleAnalyze()}
              roiCount={roiSelections.length}
              workflowState={workflowState}
            />
          </div>
        </div>
      </section>

      <AnalyzerTechnicalDrawer
        analysis={analysis}
        onClose={() => setDrawerOpen(false)}
        onOpenLightbox={(src, label) => setLightbox({ src, label })}
        open={drawerOpen}
      />

      {lightbox ? (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-950/85 p-6">
          <button
            type="button"
            onClick={() => setLightbox(null)}
            className="absolute right-6 top-6 rounded-full border border-white/10 bg-white/10 p-2 text-white transition-colors hover:bg-white/20"
          >
            <X className="h-5 w-5" />
          </button>

          <div className="w-full max-w-6xl overflow-hidden rounded-2xl border border-outline-variant/20 bg-surface-container-lowest shadow-2xl dark:border-white/10 dark:bg-[#020617]">
            <div className="border-b border-outline-variant/15 px-5 py-4 dark:border-white/10">
              <p className="text-sm font-semibold uppercase tracking-[0.26em] text-sky-300">
                Visual ampliado
              </p>
              <p className="mt-2 text-xl font-bold text-on-surface dark:text-white">
                {lightbox.label}
              </p>
            </div>
            <div className="flex max-h-[80vh] items-center justify-center bg-black p-4">
              <img
                src={lightbox.src}
                alt={lightbox.label}
                className="max-h-[76vh] w-full object-contain"
              />
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

type ImageInfoPanelProps = {
  className?: string;
  fileInputRef: React.RefObject<HTMLInputElement>;
  hasConfirmedRoi: boolean;
  loading: boolean;
  onAnalyze: () => void;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onResetRoi: () => void;
  onSelectImage: () => void;
  patientId: string;
  previewUrl: string | null;
  roiCount: number;
  selectedFile: File | null;
  setPatientId: (value: string) => void;
};

function ImageInfoPanel({
  className,
  fileInputRef,
  hasConfirmedRoi,
  loading,
  onAnalyze,
  onFileChange,
  onResetRoi,
  onSelectImage,
  patientId,
  previewUrl,
  roiCount,
  selectedFile,
  setPatientId,
}: ImageInfoPanelProps) {
  const analyzeLabel = loading
    ? "Analisando imagem"
    : hasConfirmedRoi
      ? `Iniciar analise com ${roiCount} ROI${roiCount === 1 ? "" : "s"}`
      : "Iniciar analise";

  return (
    <aside className={cn("space-y-4 lg:sticky lg:top-24 lg:self-start", className)}>
      <section className="rounded-2xl border border-heal-line bg-white p-4 shadow-soft dark:border-zinc-800 dark:bg-zinc-900">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={onFileChange}
        />

        <p className="text-xs font-bold uppercase tracking-[0.18em] text-heal-blue">
          Imagem
        </p>
        <div className="mt-3 overflow-hidden rounded-2xl border border-heal-line bg-heal-canvas dark:border-zinc-800 dark:bg-zinc-950">
          {previewUrl ? (
            <img
              src={previewUrl}
              alt="Preview da imagem selecionada"
              className="h-40 w-full object-cover"
            />
          ) : (
            <div className="flex h-40 flex-col items-center justify-center px-4 text-center">
              <FileImage className="h-8 w-8 text-heal-blue" />
              <p className="mt-3 text-sm font-black text-heal-ink dark:text-white">
                Nenhuma imagem
              </p>
              <p className="mt-1 text-xs leading-5 text-heal-muted dark:text-zinc-400">
                Envie uma foto com boa iluminacao.
              </p>
            </div>
          )}
        </div>

        <div className="mt-4 flex flex-col gap-3">
          <Button
            type="button"
            variant="secondary"
            className="w-full justify-center"
            onClick={onSelectImage}
          >
            <ImagePlus className="h-4 w-4" />
            {previewUrl ? "Trocar imagem" : "Selecionar imagem"}
          </Button>
          <Button
            type="button"
            className="w-full justify-center"
            onClick={onAnalyze}
            disabled={!selectedFile || !roiCount || loading}
            title={
              roiCount
                ? "Executar analise usando as ROIs salvas."
                : "Salve pelo menos 1 ROI para iniciar a analise."
            }
          >
            {loading ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <ScanSearch className="h-4 w-4" />
            )}
            {analyzeLabel}
          </Button>
          {!roiCount ? (
            <p className="rounded-xl bg-heal-canvas px-3 py-2 text-xs leading-5 text-heal-muted dark:bg-zinc-950 dark:text-zinc-400">
              Marque e salve pelo menos 1 ROI para liberar a analise.
            </p>
          ) : null}
        </div>
      </section>

      <section className="rounded-2xl border border-heal-line bg-white p-4 shadow-soft dark:border-zinc-800 dark:bg-zinc-900">
        <label className="text-sm font-black text-heal-ink dark:text-white">
          ID do paciente
        </label>
        <p className="mt-1 text-xs leading-5 text-heal-muted dark:text-zinc-400">
          Campo opcional para vincular esta analise.
        </p>
        <Input
          className="mt-3"
          placeholder="Ex.: patient-123"
          value={patientId}
          onChange={(event) => setPatientId(event.target.value)}
        />
      </section>

      {selectedFile ? (
        <section className="rounded-2xl border border-heal-line bg-white p-4 shadow-soft dark:border-zinc-800 dark:bg-zinc-900">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-heal-muted">
            Arquivo atual
          </p>
          <p className="mt-2 truncate text-sm font-black text-heal-ink dark:text-white" title={selectedFile.name}>
            {selectedFile.name}
          </p>
          <p className="mt-1 text-xs text-heal-muted dark:text-zinc-400">
            {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
          </p>
        </section>
      ) : null}

      <section className="rounded-2xl border border-heal-line bg-white p-4 shadow-soft dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-heal-muted">
              ROIs
            </p>
            <p className="mt-1 text-sm font-black text-heal-ink dark:text-white">
              {getRoiCountLabel(roiCount)}
            </p>
          </div>
          {roiCount ? (
            <span className="rounded-full bg-heal-tealSoft px-3 py-1 text-xs font-black text-heal-teal">
              Prontas
            </span>
          ) : null}
        </div>
        {roiCount ? (
          <button
            type="button"
            onClick={onResetRoi}
            className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-heal-line bg-white px-3 py-2 text-sm font-bold text-heal-ink transition hover:bg-heal-canvas dark:border-zinc-800 dark:bg-zinc-950 dark:text-white dark:hover:bg-zinc-800"
          >
            <RefreshCcw className="h-4 w-4" />
            Limpar todas
          </button>
        ) : null}
      </section>

      <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4 shadow-soft dark:border-amber-500/20 dark:bg-amber-500/10">
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 h-5 w-5 text-amber-600 dark:text-amber-300" />
          <p className="text-sm leading-6 text-amber-900 dark:text-amber-50">
            Apoio a decisao clinica, sem substituir avaliacao profissional.
          </p>
        </div>
      </section>

      <section className="rounded-2xl border border-heal-line bg-white p-4 shadow-soft dark:border-zinc-800 dark:bg-zinc-900">
        <p className="text-sm font-black text-heal-ink dark:text-white">Dicas de marcacao</p>
        <div className="mt-3 space-y-2">
          {captureTips.map((tip) => (
            <p
              key={tip}
              className="rounded-xl border border-heal-line bg-heal-canvas px-3 py-2 text-xs leading-5 text-heal-muted dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400"
            >
              {tip}
            </p>
          ))}
        </div>
      </section>
    </aside>
  );
}

function RoiCanvasPanel({
  children,
  editingRoiIndex,
  hasImage,
  onEditRoi,
  onNewRoi,
  onRemoveRoi,
  roiFeedback,
  roiSelections,
}: {
  children: ReactNode;
  editingRoiIndex: number | null;
  hasImage: boolean;
  onEditRoi: (index: number) => void;
  onNewRoi: () => void;
  onRemoveRoi: (index: number) => void;
  roiFeedback: string | null;
  roiSelections: HealAnalyzerRoiSelection[];
}) {
  const roiCount = roiSelections.length;

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-heal-line bg-white p-4 shadow-soft dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-heal-muted">
              Workspace ROI
            </p>
            <h2 className="mt-1 text-xl font-black text-heal-ink dark:text-white">
              Canvas principal
            </h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {roiFeedback ? (
              <span className="inline-flex items-center gap-2 rounded-full border border-heal-teal/20 bg-heal-tealSoft px-3 py-1.5 text-xs font-black text-heal-teal">
                <BadgeCheck className="h-3.5 w-3.5" />
                {roiFeedback}
              </span>
            ) : null}
            <span
              className={cn(
                "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-black",
                roiCount
                  ? "border-heal-teal/20 bg-heal-tealSoft text-heal-teal"
                  : "border-heal-line bg-heal-canvas text-heal-muted dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400",
              )}
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              {getRoiCountLabel(roiCount)}
            </span>
            {hasImage && roiCount ? (
              <button
                type="button"
                onClick={onNewRoi}
                className="inline-flex items-center gap-2 rounded-full border border-heal-line bg-white px-3 py-1.5 text-xs font-black text-heal-ink transition hover:border-heal-blue/40 hover:bg-heal-canvas dark:border-zinc-800 dark:bg-zinc-950 dark:text-white dark:hover:bg-zinc-800"
              >
                <Plus className="h-3.5 w-3.5" />
                Nova ROI
              </button>
            ) : null}
          </div>
        </div>

        {roiSelections.length ? (
          <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
            {roiSelections.map((selection, index) => {
              const active = editingRoiIndex === index;
              return (
                <div
                  key={`roi-chip-${index}-${selection.points.length}`}
                  className={cn(
                    "inline-flex shrink-0 items-center gap-2 rounded-full border px-2 py-1",
                    active
                      ? "border-heal-blue/30 bg-heal-softBlue text-heal-blue"
                      : "border-heal-line bg-heal-canvas text-heal-ink dark:border-zinc-800 dark:bg-zinc-950 dark:text-white",
                  )}
                >
                  <button
                    type="button"
                    onClick={() => onEditRoi(index)}
                    className="rounded-full px-2 py-1 text-xs font-black"
                    title={`Editar ROI ${index + 1}`}
                  >
                    ROI {index + 1} - {roiToolLabel(selection.tool)}
                  </button>
                  <button
                    type="button"
                    onClick={() => onRemoveRoi(index)}
                    className="rounded-full p-1 text-heal-muted transition hover:bg-white hover:text-heal-danger dark:hover:bg-zinc-900"
                    title={`Remover ROI ${index + 1}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              );
            })}
          </div>
        ) : null}
      </div>

      {children}
    </section>
  );
}

function EmptyCanvasPanel() {
  return (
    <section className="flex min-h-[520px] items-center justify-center rounded-2xl border border-dashed border-heal-line bg-white p-6 text-center shadow-soft dark:border-zinc-800 dark:bg-zinc-900">
      <div className="max-w-sm">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue">
          <FileImage className="h-7 w-7" />
        </div>
        <h2 className="mt-5 text-xl font-black text-heal-ink dark:text-white">
          Selecione uma imagem para iniciar
        </h2>
        <p className="mt-2 text-sm leading-6 text-heal-muted dark:text-zinc-400">
          O canvas de marcacao aparece aqui assim que a foto da ferida for carregada.
        </p>
      </div>
    </section>
  );
}

function MobileAnalyzerTabs({
  activePanel,
  onChange,
  roiCount,
}: {
  activePanel: MobilePanel;
  onChange: (panel: MobilePanel) => void;
  roiCount: number;
}) {
  const tabs: Array<{ id: MobilePanel; label: string }> = [
    { id: "image", label: "Imagem" },
    { id: "roi", label: `ROI${roiCount ? ` (${roiCount})` : ""}` },
    { id: "result", label: "Resultado" },
  ];

  return (
    <div className="flex gap-2 overflow-x-auto rounded-2xl border border-heal-line bg-white p-1 shadow-soft dark:border-zinc-800 dark:bg-zinc-900 lg:hidden">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={cn(
            "h-10 min-w-28 rounded-xl px-4 text-sm font-black transition",
            activePanel === tab.id
              ? "bg-heal-blue text-white shadow-sm"
              : "text-heal-muted hover:bg-heal-canvas hover:text-heal-ink dark:hover:bg-zinc-800 dark:hover:text-white",
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
