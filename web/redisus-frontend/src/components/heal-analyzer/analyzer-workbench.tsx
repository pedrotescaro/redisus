/* eslint-disable @next/next/no-img-element */
"use client";

import type { ChangeEvent } from "react";
import { useEffect, useRef, useState } from "react";
import {
  BrainCircuit,
  CheckCircle2,
  FileImage,
  ImagePlus,
  Layers3,
  LoaderCircle,
  PenTool,
  PencilLine,
  Plus,
  RefreshCcw,
  ScanSearch,
  ShieldAlert,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { AnalyzerRoiEditor } from "./roi-editor";
import { AnalyzerSummary } from "./analyzer-summary";
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
import {
  analyzeWithHealAnalyzer,
  type HealAnalyzerResult,
} from "../../services/ai/heal-analyzer-service";

const stepCards = [
  {
    key: "upload",
    title: "1. Upload da imagem",
    caption: "Envie a foto e confira o preview imediato.",
    icon: Upload,
  },
  {
    key: "roi",
    title: "2. Delimitacao manual",
    caption: "Marque uma ou mais feridas antes de rodar a IA.",
    icon: PenTool,
  },
  {
    key: "processing",
    title: "3. Processamento da IA",
    caption: "A pipeline usa todas as ROIs confirmadas como filtro principal.",
    icon: BrainCircuit,
  },
  {
    key: "result",
    title: "4. Resultado clinico",
    caption: "A tela destaca o tecido predominante e a confianca.",
    icon: CheckCircle2,
  },
  {
    key: "technical",
    title: "5. Detalhes tecnicos",
    caption: "A gaveta lateral guarda o conteudo tecnico sem atrapalhar o principal.",
    icon: Layers3,
  },
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

export function AnalyzerWorkbench() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
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
  };

  const handleResetRoi = () => {
    resetAnalysisPreview();
    setError(null);
    setEditingRoiIndex(null);
    setRoiSelections([]);
    setWorkflowState(previewUrl ? "marking" : "idle");
    setRoiEditorKey((current) => current + 1);
  };

  const handleStartNewRoi = () => {
    resetAnalysisPreview();
    setEditingRoiIndex(null);
    setError(null);
    setRoiEditorKey((current) => current + 1);
    setWorkflowState(previewUrl ? (roiSelections.length ? "ready" : "marking") : "idle");
  };

  const handleEditSavedRoi = (index: number) => {
    if (!roiSelections[index]) return;
    resetAnalysisPreview();
    setError(null);
    setEditingRoiIndex(index);
    setRoiEditorKey((current) => current + 1);
    setWorkflowState("ready");
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
  };

  const handleAnalyze = async () => {
    if (!selectedFile) return;

    if (!roiSelections.length) {
      setError("Confirme pelo menos uma area marcada da ferida antes de iniciar a analise.");
      setWorkflowState("marking");
      return;
    }

    setWorkflowState("loading");
    setError(null);

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
    } catch (analysisError) {
      const message =
        analysisError instanceof Error
          ? analysisError.message
          : "Falha ao executar a analise da imagem.";
      setError(message);
      setWorkflowState("error");
    }
  };

  return (
    <>
      <section className="space-y-6">
        <div className="overflow-hidden rounded-[32px] border border-primary/10 bg-[radial-gradient(circle_at_top_left,_rgba(33,150,243,0.18),_transparent_30%),radial-gradient(circle_at_top_right,_rgba(65,96,132,0.16),_transparent_30%),linear-gradient(180deg,rgba(247,250,255,0.98),rgba(229,238,249,0.98))] p-5 shadow-ambient dark:border-white/10 dark:bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.2),_transparent_32%),radial-gradient(circle_at_top_right,_rgba(79,70,229,0.18),_transparent_28%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] sm:p-6 xl:p-8">
          <div className="flex flex-col gap-6 2xl:flex-row 2xl:items-end 2xl:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs font-semibold uppercase tracking-[0.32em] text-primary dark:text-sky-300">
                HEAL analyzer
              </p>
              <h1 className="mt-3 text-3xl font-extrabold leading-tight text-slate-900 dark:text-white sm:text-4xl">
                Analise de feridas com foco em imagem, clareza e explicabilidade
              </h1>
              <p className="mt-4 text-sm leading-7 text-slate-700 dark:text-slate-300 sm:text-base sm:leading-8">
                O fluxo agora inclui uma delimitacao manual obrigatoria de uma ou
                mais lesoes para reduzir falsos positivos perifericos antes da
                segmentacao automatica.
              </p>
            </div>

            <div
              className={`inline-flex max-w-fit items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold ${status.tone}`}
            >
              {loading ? (
                <LoaderCircle className="h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle2 className="h-4 w-4" />
              )}
              <span>{status.label}</span>
            </div>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-2 2xl:grid-cols-5">
            {stepCards.map((item) => {
              const Icon = item.icon;
              const active =
                (item.key === "upload" && hasImage) ||
                (item.key === "roi" && (hasImage || hasConfirmedRoi || loading || Boolean(analysis))) ||
                (item.key === "processing" && (loading || Boolean(analysis))) ||
                ((item.key === "result" || item.key === "technical") && Boolean(analysis));

              return (
                <div
                  key={item.key}
                  className={`rounded-[24px] border p-5 ${
                    active
                      ? "border-primary/20 bg-primary/10 dark:border-sky-400/30 dark:bg-sky-400/10"
                      : "border-outline-variant/20 bg-white/65 dark:border-white/10 dark:bg-white/5"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary dark:bg-black/20 dark:text-white">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-900 dark:text-white">
                        {item.title}
                      </p>
                      <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                        {item.caption}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(280px,320px)_minmax(0,1fr)] 2xl:grid-cols-[minmax(280px,320px)_minmax(0,1fr)_minmax(300px,340px)]">
          <div className="space-y-6 xl:sticky xl:top-28 xl:self-start">
            <section className="rounded-[28px] border border-outline-variant/20 bg-surface-container-lowest/90 p-5 shadow-ambient dark:border-white/10 dark:bg-surface-container-lowest/80">
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-primary">
                Entrada
              </p>
              <h2 className="mt-3 text-2xl font-extrabold text-on-surface">
                Upload da imagem
              </h2>
              <p className="mt-2 text-sm leading-7 text-on-surface-variant">
                Escolha uma foto da ferida, confirme manualmente cada area de lesao
                no painel central e so entao libere a pipeline automatica.
              </p>

              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleFileChange}
              />

              <div className="mt-5 rounded-[24px] border border-dashed border-outline-variant/25 bg-surface-container p-4 dark:border-white/10 dark:bg-white/5">
                {previewUrl ? (
                  <div className="overflow-hidden rounded-[20px] border border-outline-variant/15 dark:border-white/10">
                    <img
                      src={previewUrl}
                      alt="Preview da imagem selecionada"
                      className="h-48 w-full object-cover sm:h-56"
                    />
                  </div>
                ) : (
                  <div className="flex h-48 flex-col items-center justify-center rounded-[20px] bg-[linear-gradient(180deg,#f2f7ff_0%,#e6eef9_100%)] px-4 text-center dark:bg-[linear-gradient(180deg,#0b1322_0%,#08111f_100%)] sm:h-56">
                    <FileImage className="h-10 w-10 text-primary dark:text-slate-300" />
                    <p className="mt-4 text-sm font-semibold text-slate-900 dark:text-white">
                      Nenhuma imagem selecionada
                    </p>
                    <p className="mt-2 max-w-[220px] text-sm text-slate-600 dark:text-slate-300">
                      Envie uma foto com boa iluminacao e foco na lesao.
                    </p>
                  </div>
                )}

                <div className="mt-4 flex flex-col gap-3">
                  <Button
                    type="button"
                    className="w-full justify-center"
                    onClick={handleSelectImage}
                  >
                    <ImagePlus className="h-4 w-4" />
                    {previewUrl ? "Trocar imagem" : "Selecionar imagem"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full justify-center"
                    onClick={() => void handleAnalyze()}
                    disabled={!selectedFile || !roiSelections.length || loading}
                  >
                    {loading ? (
                      <LoaderCircle className="h-4 w-4 animate-spin" />
                    ) : (
                      <ScanSearch className="h-4 w-4" />
                    )}
                    {roiSelections.length
                      ? `Iniciar analise (${roiSelections.length} ROI${roiSelections.length > 1 ? "s" : ""})`
                      : "Confirme ao menos uma ROI para analisar"}
                  </Button>
                </div>
              </div>

              <div className="mt-5">
                <label className="text-sm font-semibold text-on-surface">
                  ID do paciente (opcional)
                </label>
                <p className="mt-1 text-xs text-on-surface-variant">
                  Use este campo apenas se quiser vincular a analise a um paciente.
                </p>
                <Input
                  className="mt-3"
                  placeholder="Ex.: patient-123"
                  value={patientId}
                  onChange={(event) => setPatientId(event.target.value)}
                />
              </div>

              {selectedFile ? (
                <div className="mt-5 rounded-[20px] border border-outline-variant/20 bg-surface-container p-4 dark:border-white/10">
                  <p className="text-xs uppercase tracking-[0.24em] text-on-surface-variant">
                    Arquivo atual
                  </p>
                  <p className="mt-2 text-sm font-semibold text-on-surface">
                    {selectedFile.name}
                  </p>
                  <p className="mt-1 text-xs text-on-surface-variant">
                    {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              ) : null}

              {hasImage ? (
                <div className="mt-5 rounded-[20px] border border-outline-variant/20 bg-surface-container p-4 dark:border-white/10">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.24em] text-on-surface-variant">
                        Delimitacao manual
                      </p>
                      <p className="mt-2 text-sm font-semibold text-on-surface">
                        {hasConfirmedRoi
                          ? `${roiSelections.length} ROI${roiSelections.length > 1 ? "s" : ""} confirmada${roiSelections.length > 1 ? "s" : ""}`
                          : "Nenhuma ROI confirmada"}
                      </p>
                      <p className="mt-1 text-xs text-on-surface-variant">
                        {editingRoiIndex !== null
                          ? `Editando a ROI ${editingRoiIndex + 1}. Confirme novamente para atualizar essa lesao.`
                          : hasConfirmedRoi
                            ? "Voce pode adicionar outras ROIs, editar uma existente ou limpar tudo antes da analise."
                            : "Use o painel central para desenhar cada area real da lesao."}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {hasConfirmedRoi ? (
                        <button
                          type="button"
                          onClick={handleStartNewRoi}
                          className="inline-flex items-center gap-2 rounded-full border border-outline-variant/20 bg-surface-container-high px-3 py-2 text-xs font-semibold text-on-surface transition-colors hover:bg-surface-container-lowest dark:border-white/10 dark:bg-white/5 dark:hover:bg-white/10"
                        >
                          <Plus className="h-4 w-4" />
                          Nova ROI
                        </button>
                      ) : null}
                      {hasConfirmedRoi ? (
                        <button
                          type="button"
                          onClick={handleResetRoi}
                          className="inline-flex items-center gap-2 rounded-full border border-outline-variant/20 bg-surface-container-high px-3 py-2 text-xs font-semibold text-on-surface transition-colors hover:bg-surface-container-lowest dark:border-white/10 dark:bg-white/5 dark:hover:bg-white/10"
                        >
                          <RefreshCcw className="h-4 w-4" />
                          Limpar tudo
                        </button>
                      ) : null}
                    </div>
                  </div>

                  {roiSelections.length ? (
                    <div className="mt-4 space-y-3">
                      {roiSelections.map((selection, index) => {
                        const isEditing = editingRoiIndex === index;
                        return (
                          <div
                            key={`roi-card-${index}-${selection.points.length}`}
                            className={`rounded-[18px] border px-4 py-3 ${
                              isEditing
                                ? "border-primary/30 bg-primary/10 dark:border-sky-400/30 dark:bg-sky-400/10"
                                : "border-outline-variant/20 bg-surface-container-high dark:border-white/10 dark:bg-white/5"
                            }`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="text-sm font-semibold text-on-surface">
                                  ROI {index + 1} â€¢ {roiToolLabel(selection.tool)}
                                </p>
                                <p className="mt-1 text-xs text-on-surface-variant">
                                  Area aproximada: {Math.round((selection.area_ratio || 0) * 100)}% da imagem.
                                </p>
                              </div>
                              <div className="flex gap-2">
                                <button
                                  type="button"
                                  onClick={() => handleEditSavedRoi(index)}
                                  className="inline-flex items-center gap-1 rounded-full border border-outline-variant/20 bg-surface-container px-3 py-1.5 text-[11px] font-semibold text-on-surface transition-colors hover:bg-surface-container-lowest dark:border-white/10 dark:bg-white/5 dark:hover:bg-white/10"
                                >
                                  <PencilLine className="h-3.5 w-3.5" />
                                  Editar
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleRemoveSavedRoi(index)}
                                  className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-50 px-3 py-1.5 text-[11px] font-semibold text-red-700 transition-colors hover:bg-red-100 dark:border-red-500/25 dark:bg-red-500/10 dark:text-red-200 dark:hover:bg-red-500/15"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                  Remover
                                </button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : null}
                </div>
              ) : null}

              {error ? (
                <div className="mt-5 rounded-[20px] border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200">
                  {error}
                </div>
              ) : null}
            </section>

            <section className="rounded-[28px] border border-outline-variant/20 bg-surface-container-lowest/90 p-5 shadow-ambient dark:border-white/10 dark:bg-surface-container-lowest/80">
              <p className="text-sm font-semibold text-on-surface">Como capturar melhor</p>
              <ul className="mt-4 space-y-3 text-sm leading-7 text-on-surface-variant">
                <li className="rounded-2xl border border-outline-variant/20 bg-surface-container px-4 py-3 dark:border-white/10 dark:bg-white/5">
                  Evite sombras fortes e reflexos sobre o leito.
                </li>
                <li className="rounded-2xl border border-outline-variant/20 bg-surface-container px-4 py-3 dark:border-white/10 dark:bg-white/5">
                  Aproxime a camera o suficiente para mostrar textura e cor.
                </li>
                <li className="rounded-2xl border border-outline-variant/20 bg-surface-container px-4 py-3 dark:border-white/10 dark:bg-white/5">
                  Se houver mais de uma lesao, adicione uma ROI para cada ferida e mantenha pele sadia e fundo fora das marcacoes.
                </li>
              </ul>
            </section>

            <section className="rounded-[28px] border border-amber-200 bg-amber-50 p-5 shadow-ambient dark:border-amber-500/20 dark:bg-amber-500/10">
              <div className="flex items-start gap-3">
                <ShieldAlert className="mt-1 h-5 w-5 text-amber-600 dark:text-amber-300" />
                <div>
                  <p className="text-lg font-bold text-amber-900 dark:text-amber-100">
                    Aviso clinico
                  </p>
                  <p className="mt-2 text-sm leading-7 text-amber-800 dark:text-amber-50/85">
                    Este sistema apoia a decisao clinica, mas nao substitui a avaliacao
                    profissional. Use o resultado como suporte visual e interpretativo.
                  </p>
                </div>
              </div>
            </section>
          </div>

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
                    ? `Adicionar ROI ${roiSelections.length + 1}`
                    : "Confirmar primeira ROI"
              }
              disabled={loading}
              imageSrc={previewUrl}
              initialSelection={activeEditorSelection}
              savedSelections={roiSelections}
              onConfirm={handleRoiConfirmed}
              onSelectionCleared={handleRoiCleared}
            />
          ) : (
            <AnalyzerViewer
              activeTab={activeTab}
              detectionImage={null}
              loading={loading}
              onOpenLightbox={(src, label) => setLightbox({ src, label })}
              onTabChange={setActiveTab}
              tabs={viewerTabs}
              tissueLegend={tissueLegend}
            />
          )}

          <AnalyzerSummary
            analysis={analysis}
            error={error}
            hasConfirmedRoi={hasConfirmedRoi}
            hasImage={hasImage}
            loading={loading}
            onOpenTechnical={() => setDrawerOpen(true)}
            onRunAnalysis={() => void handleAnalyze()}
            workflowState={workflowState}
          />
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

          <div className="w-full max-w-6xl overflow-hidden rounded-[28px] border border-outline-variant/20 bg-surface-container-lowest shadow-2xl dark:border-white/10 dark:bg-[#020617]">
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

