/* eslint-disable @next/next/no-img-element */
"use client";

import type { ReactNode } from "react";
import { Activity, BrainCircuit, FileBarChart2, X } from "lucide-react";
import type { HealAnalyzerResult } from "../../services/ai/heal-analyzer-service";
import {
  getConfidencePercent,
  getTissueBreakdown,
  presentClinicalLabel,
  presentModelDetails,
} from "./presenter";

type AnalyzerTechnicalDrawerProps = {
  analysis: HealAnalyzerResult | null;
  onClose: () => void;
  onOpenLightbox: (src: string, label: string) => void;
  open: boolean;
};

const termDefinitions = [
  {
    title: "Mapa de atenção da IA",
    body: "Mostra as regiões que tiveram maior peso para a decisão automática. Áreas mais quentes tendem a influenciar mais a classificação.",
  },
  {
    title: "Margem de confianca",
    body: "Indica o quanto a melhor resposta ficou acima da segunda melhor hipotese. Quanto maior a margem, menor a ambiguidade.",
  },
  {
    title: "Entropia de confianca",
    body: "Resume o nível de dispersão entre as probabilidades do modelo. Valores mais altos sugerem maior incerteza.",
  },
  {
    title: "Fallback",
    body: "Sinaliza quando o pipeline precisou usar uma rota de segurança porque o classificador principal não entregou uma resposta forte o suficiente.",
  },
];

type DetailSectionProps = {
  children: ReactNode;
  defaultOpen?: boolean;
  subtitle: string;
  title: string;
};

function DetailSection({
  children,
  defaultOpen = false,
  subtitle,
  title,
}: DetailSectionProps) {
  return (
    <details
      open={defaultOpen}
      className="rounded-[22px] border border-outline-variant/20 bg-surface-container p-4 dark:border-white/10"
    >
      <summary className="cursor-pointer list-none">
        <p className="text-sm font-semibold text-on-surface">{title}</p>
        <p className="mt-1 text-xs text-on-surface-variant">{subtitle}</p>
      </summary>
      <div className="mt-4">{children}</div>
    </details>
  );
}

export function AnalyzerTechnicalDrawer({
  analysis,
  onClose,
  onOpenLightbox,
  open,
}: AnalyzerTechnicalDrawerProps) {
  const tissueBreakdown = getTissueBreakdown(analysis);
  const confidence = analysis ? getConfidencePercent(analysis.inference.confidence) : 0;

  return (
    <>
      <div
        aria-hidden="true"
        className={`fixed inset-0 z-[70] bg-black/60 transition-opacity ${
          open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onClose}
      />

      <aside
        aria-hidden={!open}
        className={`fixed right-0 top-0 z-[80] h-screen w-full max-w-[540px] transform border-l border-outline-variant/20 bg-surface-container-lowest/95 text-on-surface shadow-2xl backdrop-blur transition-transform dark:border-white/10 dark:bg-[#0b1220]/95 dark:text-white ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex h-full flex-col">
          <div className="flex items-start justify-between gap-4 border-b border-outline-variant/15 px-6 py-5 dark:border-white/10">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-primary">
                Detalhes tecnicos
              </p>
              <h2 className="mt-2 text-2xl font-extrabold text-on-surface dark:text-white">
                Como a IA chegou a esta leitura
              </h2>
              <p className="mt-2 text-sm text-on-surface-variant dark:text-slate-300">
                Esta area guarda as probabilidades completas, visuais tecnicos e metricas
                do modelo sem poluir a tela principal.
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-outline-variant/20 bg-surface-container p-2 text-on-surface transition-colors hover:bg-surface-container-high dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
            {!analysis ? (
              <div className="rounded-[22px] border border-dashed border-outline-variant/20 bg-surface-container px-5 py-6 text-sm text-on-surface-variant dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
                Execute uma análise para liberar os dados técnicos desta gaveta.
              </div>
            ) : (
              <>
                <DetailSection
                  defaultOpen
                  title="Probabilidades completas"
                  subtitle="Distribuição por tecido com base na segmentação e no classificador."
                >
                  <div className="space-y-3">
                    {tissueBreakdown.map((item) => (
                      <div
                        key={item.label}
                        className="rounded-2xl border border-outline-variant/20 bg-surface-container-high px-3 py-3 dark:border-white/10 dark:bg-white/5"
                      >
                        <div className="flex items-center justify-between gap-4">
                          <div className="flex items-center gap-3">
                            <span
                              className="h-3 w-3 rounded-full"
                              style={{ backgroundColor: item.color }}
                            />
                            <span className="text-sm font-semibold text-on-surface dark:text-white">
                              {item.label}
                            </span>
                          </div>
                          <span className="text-sm font-semibold text-on-surface dark:text-white">
                            {item.value.toFixed(1)}%
                          </span>
                        </div>
                        <div className="mt-3 h-2 overflow-hidden rounded-full bg-outline-variant/20 dark:bg-white/10">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${Math.max(0, Math.min(100, item.value))}%`,
                              backgroundColor: item.color,
                            }}
                          />
                        </div>
                        {item.description ? (
                          <p className="mt-3 text-xs leading-6 text-on-surface-variant dark:text-slate-300">{item.description}</p>
                        ) : null}
                        {item.action ? (
                          <p className="mt-2 text-xs leading-6 text-primary dark:text-sky-200">{item.action}</p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </DetailSection>

                <DetailSection
                  title="Visuais tecnicos"
                  subtitle="As imagens abaixo ajudam a auditar o recorte e a explicabilidade."
                >
                  <div className="grid gap-4 md:grid-cols-2">
                    {analysis.visuals?.attention?.data_url ? (
                      <button
                        type="button"
                        onClick={() =>
                          onOpenLightbox(
                            analysis.visuals?.attention?.data_url as string,
                            analysis.visuals?.attention?.label || "Mapa de atenção da IA",
                          )
                        }
                        className="overflow-hidden rounded-[20px] border border-outline-variant/20 bg-surface-container text-left transition-transform hover:-translate-y-0.5 dark:border-white/10 dark:bg-white/5"
                      >
                        <img
                          src={analysis.visuals.attention.data_url}
                          alt={analysis.visuals.attention.label}
                          className="h-44 w-full object-cover"
                        />
                        <div className="px-4 py-3">
                          <p className="text-sm font-semibold text-on-surface dark:text-white">
                            {analysis.visuals.attention.label}
                          </p>
                          <p className="mt-1 text-xs leading-6 text-on-surface-variant dark:text-slate-300">
                            {analysis.visuals.attention.description}
                          </p>
                        </div>
                      </button>
                    ) : null}

                    {analysis.visuals?.detection?.data_url ? (
                      <button
                        type="button"
                        onClick={() =>
                          onOpenLightbox(
                            analysis.visuals?.detection?.data_url as string,
                            analysis.visuals?.detection?.label || "Regiao analisada",
                          )
                        }
                        className="overflow-hidden rounded-[20px] border border-outline-variant/20 bg-surface-container text-left transition-transform hover:-translate-y-0.5 dark:border-white/10 dark:bg-white/5"
                      >
                        <img
                          src={analysis.visuals.detection.data_url}
                          alt={analysis.visuals.detection.label}
                          className="h-44 w-full object-cover"
                        />
                        <div className="px-4 py-3">
                          <p className="text-sm font-semibold text-on-surface dark:text-white">
                            {analysis.visuals.detection.label}
                          </p>
                          <p className="mt-1 text-xs leading-6 text-on-surface-variant dark:text-slate-300">
                            {analysis.visuals.detection.description}
                          </p>
                        </div>
                      </button>
                    ) : null}
                  </div>

                  <div className="mt-4 rounded-2xl border border-outline-variant/20 bg-surface-container-low px-4 py-4 dark:border-white/10">
                    <p className="flex items-center gap-2 text-sm font-semibold text-on-surface dark:text-white">
                      <BrainCircuit className="h-4 w-4 text-primary" />
                      Como interpretar o mapa de atenção
                    </p>
                    <p className="mt-2 text-sm leading-7 text-on-surface-variant dark:text-slate-300">
                      Áreas mais quentes indicam as regiões que pesaram mais na decisão.
                      O mapa de atenção não substitui a avaliação clínica, mas ajuda a
                      explicar por que a IA destacou um tecido como predominante.
                    </p>
                  </div>
                </DetailSection>

                <DetailSection
                  title="Metricas do modelo"
                  subtitle="Indicadores para auditoria, confianca e rastreabilidade."
                >
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-2xl border border-outline-variant/20 bg-surface-container-high px-4 py-3 dark:border-white/10 dark:bg-white/5">
                      <p className="text-xs uppercase tracking-[0.24em] text-on-surface-variant dark:text-slate-400">Confianca</p>
                      <p className="mt-2 text-sm font-semibold text-on-surface dark:text-white">{confidence}%</p>
                    </div>
                    <div className="rounded-2xl border border-outline-variant/20 bg-surface-container-high px-4 py-3 dark:border-white/10 dark:bg-white/5">
                      <p className="text-xs uppercase tracking-[0.24em] text-on-surface-variant dark:text-slate-400">Tempo</p>
                      <p className="mt-2 text-sm font-semibold text-on-surface dark:text-white">
                        {Math.round(analysis.processing_time_ms || 0)} ms
                      </p>
                    </div>
                    <div className="rounded-2xl border border-outline-variant/20 bg-surface-container-high px-4 py-3 dark:border-white/10 dark:bg-white/5">
                      <p className="text-xs uppercase tracking-[0.24em] text-on-surface-variant dark:text-slate-400">Modelo</p>
                      <p className="mt-2 text-sm font-semibold text-on-surface dark:text-white">
                        {presentModelDetails(analysis.model_version)}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-outline-variant/20 bg-surface-container-high px-4 py-3 dark:border-white/10 dark:bg-white/5">
                      <p className="text-xs uppercase tracking-[0.24em] text-on-surface-variant dark:text-slate-400">Contrato</p>
                      <p className="mt-2 text-sm font-semibold text-on-surface dark:text-white">{analysis.contract_version}</p>
                    </div>
                    <div className="rounded-2xl border border-outline-variant/20 bg-surface-container-high px-4 py-3 dark:border-white/10 dark:bg-white/5">
                      <p className="text-xs uppercase tracking-[0.24em] text-on-surface-variant dark:text-slate-400">Margem</p>
                      <p className="mt-2 text-sm font-semibold text-on-surface dark:text-white">
                        {analysis.inference.confidence_margin.toFixed(3)}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-outline-variant/20 bg-surface-container-high px-4 py-3 dark:border-white/10 dark:bg-white/5">
                      <p className="text-xs uppercase tracking-[0.24em] text-on-surface-variant dark:text-slate-400">Entropia</p>
                      <p className="mt-2 text-sm font-semibold text-on-surface dark:text-white">
                        {analysis.inference.confidence_entropy.toFixed(3)}
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 rounded-2xl border border-outline-variant/20 bg-surface-container-low px-4 py-4 dark:border-white/10">
                    <div className="flex items-start gap-3">
                      <Activity className="mt-0.5 h-4 w-4 text-primary" />
                      <div>
                        <p className="text-sm font-semibold text-on-surface dark:text-white">
                          {presentClinicalLabel(analysis.primary_tissue)}
                        </p>
                        <p className="mt-2 text-sm leading-7 text-on-surface-variant dark:text-slate-300">
                          {analysis.primary_justification || analysis.interpretation.summary}
                        </p>
                      </div>
                    </div>
                  </div>
                </DetailSection>

                <DetailSection
                  title="Termos tecnicos"
                  subtitle="Glossario rapido para quem quiser aprofundar a leitura."
                >
                  <div className="space-y-3">
                    {termDefinitions.map((item) => (
                      <div
                        key={item.title}
                        className="rounded-2xl border border-outline-variant/20 bg-surface-container-high px-4 py-4 dark:border-white/10 dark:bg-white/5"
                      >
                        <p className="flex items-center gap-2 text-sm font-semibold text-on-surface dark:text-white">
                          <FileBarChart2 className="h-4 w-4 text-primary" />
                          {item.title}
                        </p>
                        <p className="mt-2 text-sm leading-7 text-on-surface-variant dark:text-slate-300">{item.body}</p>
                      </div>
                    ))}
                  </div>
                </DetailSection>
              </>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}

