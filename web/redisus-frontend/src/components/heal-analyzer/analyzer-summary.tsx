"use client";

import {
  Activity,
  BrainCircuit,
  ClipboardCheck,
  LoaderCircle,
  PanelRightOpen,
  Sparkles,
  Target,
} from "lucide-react";
import { Button } from "../ui/button";
import type { HealAnalyzerResult } from "../../services/ai/heal-analyzer-service";
import {
  getConfidencePercent,
  getRiskTone,
  presentModelLabel,
  getSimpleExplanation,
  getStatusCopy,
  presentClinicalLabel,
  type WorkflowState,
} from "./presenter";

type AnalyzerSummaryProps = {
  analysis: HealAnalyzerResult | null;
  error: string | null;
  hasConfirmedRoi: boolean;
  hasImage: boolean;
  loading: boolean;
  onOpenTechnical: () => void;
  onRunAnalysis: () => void;
  roiCount: number;
  workflowState: WorkflowState;
};

export function AnalysisResultPanel({
  analysis,
  error,
  hasConfirmedRoi,
  hasImage,
  loading,
  onOpenTechnical,
  onRunAnalysis,
  roiCount,
  workflowState,
}: AnalyzerSummaryProps) {
  const status = getStatusCopy(workflowState, hasImage, hasConfirmedRoi);
  const confidence = analysis ? getConfidencePercent(analysis.inference.confidence) : 0;
  const primaryLabel = analysis
    ? analysis.is_valid_wound
      ? presentClinicalLabel(analysis.primary_tissue)
      : "Imagem precisa de revisão"
    : "Resultado ainda não gerado";

  return (
    <aside className="2xl:sticky 2xl:top-24 2xl:self-start">
      <div className="rounded-2xl border border-heal-line bg-white p-5 shadow-soft dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-heal-muted">
              Resultado
            </p>
            <h2 className="mt-2 text-xl font-black text-heal-ink dark:text-white">
              Análise clínica
            </h2>
          </div>
          <div
            className={`inline-flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-bold ${status.tone}`}
          >
            {loading ? (
              <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            <span>{status.label}</span>
          </div>
        </div>

        <div className="mt-4 rounded-2xl border border-heal-line bg-heal-canvas p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex items-center gap-2 text-sm font-bold text-heal-ink dark:text-white">
            <Target className="h-4 w-4 text-heal-teal" />
            <span>
              {roiCount
                ? `${roiCount} ROI${roiCount === 1 ? "" : "s"} pronta${roiCount === 1 ? "" : "s"}`
                : "Nenhuma ROI pronta"}
            </span>
          </div>
          <p className="mt-2 text-sm leading-6 text-heal-muted dark:text-zinc-400">
            {hasConfirmedRoi
              ? "A análise usará somente as áreas marcadas."
              : "Marque e salve uma ROI para liberar a análise."}
          </p>
        </div>

        {analysis ? (
          <>
            <div className="mt-4 rounded-2xl border border-heal-blue/20 bg-heal-softBlue/60 p-5 dark:border-sky-500/20 dark:bg-sky-500/10">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-heal-blue">
                Resultado principal
              </p>
              <h2 className="mt-3 text-2xl font-black text-heal-ink dark:text-white">
                {primaryLabel}
              </h2>
              <p className="mt-3 text-sm leading-6 text-heal-inkSecondary dark:text-zinc-300">
                {getSimpleExplanation(analysis)}
              </p>

              <div className="mt-5 flex flex-wrap gap-2">
                <span
                  className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${getRiskTone(
                      analysis.interpretation.risk_level,
                    )}`}
                  >
                    Risco {analysis.interpretation.risk_level}
                </span>
                {analysis.interpretation.requires_expert_review ? (
                  <span className="inline-flex items-center rounded-full border border-amber-500/30 bg-amber-500/15 px-3 py-1 text-xs font-semibold text-amber-300">
                    Revisão profissional recomendada
                  </span>
                ) : null}
              </div>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2 2xl:grid-cols-1">
              <div className="rounded-2xl border border-heal-line bg-heal-canvas p-4 dark:border-zinc-800 dark:bg-zinc-950">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-heal-muted">
                  Tecido detectado
                </p>
                <p className="mt-2 text-sm font-black text-heal-ink dark:text-white">
                  {presentClinicalLabel(analysis.primary_tissue)}
                </p>
              </div>
              <div className="rounded-2xl border border-heal-line bg-heal-canvas p-4 dark:border-zinc-800 dark:bg-zinc-950">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-heal-muted">
                  Modelo
                </p>
                <p className="mt-2 text-sm font-black text-heal-ink dark:text-white">
                  {presentModelLabel(analysis.model_version)}
                </p>
              </div>
            </div>

            <div className="mt-4 rounded-2xl border border-heal-line bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-black text-heal-ink dark:text-white">Confiança da IA</p>
                  <p className="mt-1 text-xs text-heal-muted dark:text-zinc-400">
                    Percentual de segurança do modelo no padrão encontrado.
                  </p>
                </div>
                <span className="text-lg font-black text-heal-ink dark:text-white">{confidence}%</span>
              </div>
              <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-heal-line dark:bg-zinc-800">
                <div
                  className="h-full rounded-full bg-heal-blue transition-all"
                  style={{ width: `${confidence}%` }}
                />
              </div>
            </div>

            <div className="mt-4 rounded-2xl border border-heal-line bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
              <div className="flex items-center gap-2 text-heal-ink dark:text-white">
                <BrainCircuit className="h-4 w-4" />
                <p className="text-sm font-black">Resumo clínico</p>
              </div>
              <p className="mt-3 text-sm leading-6 text-heal-muted dark:text-zinc-400">
                {analysis.interpretation.summary ||
                  "A IA gerou um resumo clínico da imagem analisada."}
              </p>
            </div>

            {analysis.interpretation.recommendations?.length ? (
              <div className="mt-4 rounded-2xl border border-heal-line bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
                <p className="text-sm font-black text-heal-ink dark:text-white">
                  Próximos cuidados sugeridos
                </p>
                <ul className="mt-3 space-y-2 text-sm text-heal-muted dark:text-zinc-400">
                  {analysis.interpretation.recommendations.slice(0, 3).map((item) => (
                    <li
                      key={item}
                      className="rounded-xl border border-heal-line bg-heal-canvas px-3 py-2 dark:border-zinc-800 dark:bg-zinc-900"
                    >
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="mt-4 flex flex-col gap-3">
              <Button type="button" className="w-full justify-center" onClick={onOpenTechnical}>
                <PanelRightOpen className="h-4 w-4" />
                Ver detalhes tecnicos
              </Button>
              <Button
                type="button"
                variant="outline"
                className="w-full justify-center"
                onClick={onRunAnalysis}
                disabled={loading}
              >
                {loading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
                Reexecutar análise
              </Button>
              <p className="text-center text-xs text-heal-muted dark:text-zinc-400">
                Tempo de processamento: {Math.round(analysis.processing_time_ms || 0)} ms
              </p>
            </div>
          </>
        ) : (
          <div className="mt-4 rounded-2xl border border-dashed border-heal-line bg-heal-canvas p-6 text-center dark:border-zinc-800 dark:bg-zinc-950">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-heal-blue shadow-sm dark:bg-zinc-900">
              {loading ? <LoaderCircle className="h-6 w-6 animate-spin" /> : <ClipboardCheck className="h-6 w-6" />}
            </div>
            <p className="mt-4 text-lg font-black text-heal-ink dark:text-white">
              Resultado ainda não gerado
            </p>
            <p className="mx-auto mt-2 max-w-[260px] text-sm leading-6 text-heal-muted dark:text-zinc-400">
              Marque a ROI e inicie a análise para visualizar os dados clínicos.
            </p>
            {error ? (
              <p className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-3 py-3 text-left text-sm text-red-700 dark:border-red-500/25 dark:bg-red-500/10 dark:text-red-200">
                {error}
              </p>
            ) : null}
            {hasConfirmedRoi ? (
              <Button
                type="button"
                className="mt-5 w-full justify-center"
                onClick={onRunAnalysis}
                disabled={loading}
              >
                {loading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Activity className="h-4 w-4" />}
                Iniciar análise com {roiCount} ROI{roiCount === 1 ? "" : "s"}
              </Button>
            ) : null}
          </div>
        )}
      </div>
    </aside>
  );
}

export const AnalyzerSummary = AnalysisResultPanel;

