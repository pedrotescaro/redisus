"use client";

import {
  AlertTriangle,
  BrainCircuit,
  LoaderCircle,
  PanelRightOpen,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { HealAnalyzerResult } from "@/services/ai/heal-analyzer-service";
import {
  getConfidencePercent,
  getRiskTone,
  presentModelLabel,
  getSimpleExplanation,
  getStatusCopy,
  presentClinicalLabel,
  type WorkflowState,
} from "@/components/heal-analyzer/presenter";

type AnalyzerSummaryProps = {
  analysis: HealAnalyzerResult | null;
  error: string | null;
  hasImage: boolean;
  loading: boolean;
  onOpenTechnical: () => void;
  onRunAnalysis: () => void;
  workflowState: WorkflowState;
};

export function AnalyzerSummary({
  analysis,
  error,
  hasImage,
  loading,
  onOpenTechnical,
  onRunAnalysis,
  workflowState,
}: AnalyzerSummaryProps) {
  const status = getStatusCopy(workflowState, hasImage);
  const confidence = analysis ? getConfidencePercent(analysis.inference.confidence) : 0;

  return (
    <aside className="lg:sticky lg:top-28">
      <div className="rounded-[28px] border border-white/10 bg-surface-container-lowest/80 p-5 shadow-ambient">
        <div
          className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${status.tone}`}
        >
          {loading ? (
            <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Sparkles className="h-3.5 w-3.5" />
          )}
          <span>{status.label}</span>
        </div>

        <p className="mt-3 text-sm text-on-surface-variant">{status.caption}</p>

        {analysis ? (
          <>
            <div className="mt-6 rounded-[24px] border border-white/10 bg-[linear-gradient(160deg,rgba(14,165,233,0.12),rgba(15,23,42,0.2))] p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-300">
                Resultado clinico
              </p>
              <h2 className="mt-3 text-3xl font-extrabold text-white">
                {analysis.is_valid_wound
                  ? presentClinicalLabel(analysis.primary_tissue)
                  : "Imagem precisa de revisao"}
              </h2>
              <p className="mt-3 text-sm leading-7 text-slate-200">
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
                    Revisao profissional recomendada
                  </span>
                ) : null}
              </div>
            </div>

            <div className="mt-5 rounded-[24px] border border-white/10 bg-surface-container p-5">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-on-surface">Confianca da IA</p>
                  <p className="mt-1 text-xs text-on-surface-variant">
                    Percentual de seguranca do modelo no padrao encontrado.
                  </p>
                </div>
                <span className="text-lg font-bold text-on-surface">{confidence}%</span>
              </div>
              <div className="mt-4 h-3 overflow-hidden rounded-full bg-white/8">
                <div
                  className="h-full rounded-full bg-[linear-gradient(90deg,#14b8a6_0%,#38bdf8_50%,#6366f1_100%)] transition-all"
                  style={{ width: `${confidence}%` }}
                />
              </div>
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
              <div className="rounded-[22px] border border-white/10 bg-surface-container p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-on-surface-variant">
                  Modelo
                </p>
                <p className="mt-2 text-sm font-semibold text-on-surface">
                  {presentModelLabel(analysis.model_version)}
                </p>
              </div>
              <div className="rounded-[22px] border border-white/10 bg-surface-container p-4">
                <p className="text-xs uppercase tracking-[0.24em] text-on-surface-variant">
                  Tempo
                </p>
                <p className="mt-2 text-sm font-semibold text-on-surface">
                  {Math.round(analysis.processing_time_ms || 0)} ms
                </p>
              </div>
            </div>

            <div className="mt-5 rounded-[24px] border border-white/10 bg-surface-container p-5">
              <div className="flex items-center gap-2 text-on-surface">
                <BrainCircuit className="h-4 w-4" />
                <p className="text-sm font-semibold">Resumo em linguagem simples</p>
              </div>
              <p className="mt-3 text-sm leading-7 text-on-surface-variant">
                {analysis.interpretation.summary ||
                  "A IA gerou um resumo clinico da imagem analisada."}
              </p>
            </div>

            {analysis.interpretation.recommendations?.length ? (
              <div className="mt-5 rounded-[24px] border border-white/10 bg-surface-container p-5">
                <p className="text-sm font-semibold text-on-surface">
                  Proximos cuidados sugeridos
                </p>
                <ul className="mt-3 space-y-3 text-sm text-on-surface-variant">
                  {analysis.interpretation.recommendations.slice(0, 3).map((item) => (
                    <li
                      key={item}
                      className="rounded-2xl border border-white/10 bg-white/5 px-3 py-3"
                    >
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="mt-5 flex flex-col gap-3">
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
                Reexecutar analise
              </Button>
            </div>
          </>
        ) : (
          <div className="mt-6 rounded-[24px] border border-dashed border-white/10 bg-surface-container p-5">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-1 h-5 w-5 text-amber-300" />
              <div>
                <p className="text-lg font-bold text-on-surface">
                  Nenhum resultado em exibicao
                </p>
                <p className="mt-2 text-sm leading-7 text-on-surface-variant">
                  Esta coluna fica reservada para o tecido destacado, a confianca da IA,
                  o resumo clinico e o acesso rapido aos detalhes tecnicos.
                </p>
                {error ? (
                  <p className="mt-4 rounded-2xl border border-red-500/25 bg-red-500/10 px-3 py-3 text-sm text-red-200">
                    {error}
                  </p>
                ) : null}
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
