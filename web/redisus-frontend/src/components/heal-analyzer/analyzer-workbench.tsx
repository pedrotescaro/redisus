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
  ScanSearch,
  ShieldAlert,
  Upload,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AnalyzerSummary } from "@/components/heal-analyzer/analyzer-summary";
import { AnalyzerTechnicalDrawer } from "@/components/heal-analyzer/analyzer-technical-drawer";
import { AnalyzerViewer } from "@/components/heal-analyzer/analyzer-viewer";
import {
  getStatusCopy,
  getTissueBreakdown,
  type AnalyzerTabId,
  type WorkflowState,
} from "@/components/heal-analyzer/presenter";
import {
  analyzeWithHealAnalyzer,
  type HealAnalyzerResult,
} from "@/services/ai/heal-analyzer-service";

const stepCards = [
  {
    key: "upload",
    title: "1. Upload da imagem",
    caption: "Envie a foto e confira o preview imediato.",
    icon: Upload,
  },
  {
    key: "processing",
    title: "2. Processamento da IA",
    caption: "O pipeline monta segmentacao, resumo e mapa de atencao.",
    icon: BrainCircuit,
  },
  {
    key: "result",
    title: "3. Resultado clinico",
    caption: "A tela destaca o tecido predominante e a confianca.",
    icon: CheckCircle2,
  },
  {
    key: "technical",
    title: "4. Detalhes tecnicos",
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
  const status = getStatusCopy(workflowState, hasImage);
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

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.currentTarget.value = "";
    if (!file) return;

    const nextPreview = URL.createObjectURL(file);

    setSelectedFile(file);
    setPreviewUrl(nextPreview);
    setAnalysis(null);
    setError(null);
    setActiveTab("original");
    setDrawerOpen(false);
    setWorkflowState("ready");
  };

  const handleAnalyze = async () => {
    if (!selectedFile) return;

    setWorkflowState("loading");
    setError(null);

    try {
      const result = await analyzeWithHealAnalyzer(selectedFile, { patientId });
      setAnalysis(result);
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
        <div className="overflow-hidden rounded-[32px] border border-white/10 bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.2),_transparent_32%),radial-gradient(circle_at_top_right,_rgba(79,70,229,0.18),_transparent_28%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] p-8 shadow-ambient">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs font-semibold uppercase tracking-[0.32em] text-sky-300">
                HEAL analyzer
              </p>
              <h1 className="mt-3 text-4xl font-extrabold leading-tight text-white">
                Analise de feridas com foco em imagem, clareza e explicabilidade
              </h1>
              <p className="mt-4 text-base leading-8 text-slate-300">
                Esta tela foi desenhada para mostrar primeiro o que importa e esconder
                a parte tecnica ate o usuario pedir. O fluxo principal fica simples;
                a auditoria visual fica a um clique.
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

          <div className="mt-8 grid gap-4 lg:grid-cols-4">
            {stepCards.map((item, index) => {
              const Icon = item.icon;
              const active =
                (index === 0 && hasImage) ||
                (index === 1 && loading) ||
                (index >= 2 && analysis);

              return (
                <div
                  key={item.key}
                  className={`rounded-[24px] border p-5 ${
                    active
                      ? "border-sky-400/30 bg-sky-400/10"
                      : "border-white/10 bg-white/5"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-black/20 text-white">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-white">{item.title}</p>
                      <p className="mt-1 text-xs text-slate-300">{item.caption}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
          <div className="space-y-6">
            <section className="rounded-[28px] border border-white/10 bg-surface-container-lowest/80 p-5 shadow-ambient">
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-primary">
                Entrada
              </p>
              <h2 className="mt-3 text-2xl font-extrabold text-on-surface">
                Upload da imagem
              </h2>
              <p className="mt-2 text-sm leading-7 text-on-surface-variant">
                Escolha uma foto da ferida para iniciar a leitura visual do HEAL analyzer.
                O preview aparece imediatamente.
              </p>

              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleFileChange}
              />

              <div className="mt-5 rounded-[24px] border border-dashed border-white/10 bg-white/5 p-4">
                {previewUrl ? (
                  <div className="overflow-hidden rounded-[20px] border border-white/10">
                    <img
                      src={previewUrl}
                      alt="Preview da imagem selecionada"
                      className="h-48 w-full object-cover"
                    />
                  </div>
                ) : (
                  <div className="flex h-48 flex-col items-center justify-center rounded-[20px] bg-[#08111f] text-center">
                    <FileImage className="h-10 w-10 text-slate-300" />
                    <p className="mt-4 text-sm font-semibold text-white">
                      Nenhuma imagem selecionada
                    </p>
                    <p className="mt-2 max-w-[220px] text-sm text-slate-300">
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
                    disabled={!selectedFile || loading}
                  >
                    {loading ? (
                      <LoaderCircle className="h-4 w-4 animate-spin" />
                    ) : (
                      <ScanSearch className="h-4 w-4" />
                    )}
                    Iniciar analise
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
                <div className="mt-5 rounded-[20px] border border-white/10 bg-surface-container p-4">
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

              {error ? (
                <div className="mt-5 rounded-[20px] border border-red-500/30 bg-red-500/10 px-4 py-4 text-sm text-red-200">
                  {error}
                </div>
              ) : null}
            </section>

            <section className="rounded-[28px] border border-white/10 bg-surface-container-lowest/80 p-5 shadow-ambient">
              <p className="text-sm font-semibold text-on-surface">Como capturar melhor</p>
              <ul className="mt-4 space-y-3 text-sm leading-7 text-on-surface-variant">
                <li className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                  Evite sombras fortes e reflexos sobre o leito.
                </li>
                <li className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                  Aproxime a camera o suficiente para mostrar textura e cor.
                </li>
                <li className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                  Use o painel central para alternar entre original, segmentacao e atencao.
                </li>
              </ul>
            </section>

            <section className="rounded-[28px] border border-amber-500/20 bg-amber-500/10 p-5 shadow-ambient">
              <div className="flex items-start gap-3">
                <ShieldAlert className="mt-1 h-5 w-5 text-amber-300" />
                <div>
                  <p className="text-lg font-bold text-amber-100">Aviso clinico</p>
                  <p className="mt-2 text-sm leading-7 text-amber-50/85">
                    Este sistema apoia a decisao clinica, mas nao substitui a avaliacao
                    profissional. Use o resultado como suporte visual e interpretativo.
                  </p>
                </div>
              </div>
            </section>
          </div>

          <AnalyzerViewer
            activeTab={activeTab}
            detectionImage={analysis?.visuals?.detection?.data_url ?? null}
            loading={loading}
            onOpenLightbox={(src, label) => setLightbox({ src, label })}
            onTabChange={setActiveTab}
            tabs={viewerTabs}
            tissueLegend={tissueLegend}
          />

          <AnalyzerSummary
            analysis={analysis}
            error={error}
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
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/85 p-6">
          <button
            type="button"
            onClick={() => setLightbox(null)}
            className="absolute right-6 top-6 rounded-full border border-white/10 bg-white/10 p-2 text-white transition-colors hover:bg-white/20"
          >
            <X className="h-5 w-5" />
          </button>

          <div className="w-full max-w-6xl overflow-hidden rounded-[28px] border border-white/10 bg-[#020617] shadow-2xl">
            <div className="border-b border-white/10 px-5 py-4">
              <p className="text-sm font-semibold uppercase tracking-[0.26em] text-sky-300">
                Visual ampliado
              </p>
              <p className="mt-2 text-xl font-bold text-white">{lightbox.label}</p>
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
