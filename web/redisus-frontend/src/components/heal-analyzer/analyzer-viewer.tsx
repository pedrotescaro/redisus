/* eslint-disable @next/next/no-img-element */
"use client";

import type { ComponentType } from "react";
import { BrainCircuit, Layers3, Maximize2, ScanSearch } from "lucide-react";
import { cn } from "@/lib/utils";

type ViewerTab = {
  id: "original" | "segmentation" | "combined" | "attention";
  label: string;
  description: string;
  src: string | null;
};

type TissueLegendItem = {
  label: string;
  color: string;
  value: number;
};

type AnalyzerViewerProps = {
  activeTab: ViewerTab["id"];
  detectionImage?: string | null;
  loading: boolean;
  onOpenLightbox: (src: string, label: string) => void;
  onTabChange: (tabId: ViewerTab["id"]) => void;
  tabs: ViewerTab[];
  tissueLegend: TissueLegendItem[];
};

const tabIcons = {
  original: ScanSearch,
  segmentation: Layers3,
  combined: Layers3,
  attention: BrainCircuit,
} satisfies Record<ViewerTab["id"], ComponentType<{ className?: string }>>;

export function AnalyzerViewer({
  activeTab,
  detectionImage,
  loading,
  onOpenLightbox,
  onTabChange,
  tabs,
  tissueLegend,
}: AnalyzerViewerProps) {
  const selectedTab = tabs.find((tab) => tab.id === activeTab) ?? tabs[0];

  return (
    <section className="rounded-[28px] border border-white/10 bg-surface-container-lowest/70 p-5 shadow-ambient">
      <div className="flex flex-col gap-4 border-b border-white/10 pb-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-primary">
            Painel visual
          </p>
          <h2 className="mt-2 text-2xl font-extrabold text-on-surface">
            Imagem principal da analise
          </h2>
          <p className="mt-2 max-w-2xl text-sm text-on-surface-variant">
            A tela central mostra a foto original e as camadas geradas pela IA. As
            vistas tecnicas ficam disponiveis por aba, sem poluir a leitura principal.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {tabs.map((tab) => {
            const Icon = tabIcons[tab.id];
            const active = tab.id === selectedTab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => onTabChange(tab.id)}
                className={cn(
                  "inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition-all",
                  active
                    ? "border-primary/40 bg-primary/15 text-primary"
                    : "border-white/10 bg-white/5 text-on-surface-variant hover:border-primary/30 hover:text-on-surface",
                )}
              >
                <Icon className="h-4 w-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_280px]">
        <div className="rounded-[24px] border border-white/10 bg-[#08111f] p-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-lg font-bold text-white">{selectedTab.label}</p>
              <p className="mt-1 text-sm text-slate-300">{selectedTab.description}</p>
            </div>
            {selectedTab.src ? (
              <button
                type="button"
                onClick={() => onOpenLightbox(selectedTab.src as string, selectedTab.label)}
                className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-slate-200 transition-colors hover:bg-white/10"
              >
                <Maximize2 className="h-4 w-4" />
                Ampliar
              </button>
            ) : null}
          </div>

          <div className="mt-4 flex min-h-[440px] items-center justify-center overflow-hidden rounded-[20px] border border-white/10 bg-[radial-gradient(circle_at_top,_rgba(37,99,235,0.18),_transparent_45%),linear-gradient(180deg,#07101d_0%,#030712_100%)]">
            {loading ? (
              <div className="w-full px-8">
                <div className="h-[320px] animate-pulse rounded-[18px] bg-white/8" />
                <div className="mt-4 h-4 w-1/3 animate-pulse rounded-full bg-white/8" />
                <div className="mt-2 h-4 w-2/3 animate-pulse rounded-full bg-white/8" />
              </div>
            ) : selectedTab.src ? (
              <button
                type="button"
                onClick={() => onOpenLightbox(selectedTab.src as string, selectedTab.label)}
                className="group relative h-full w-full"
              >
                <img
                  src={selectedTab.src}
                  alt={selectedTab.label}
                  className="h-full min-h-[440px] w-full object-contain"
                />
                <div className="pointer-events-none absolute inset-x-6 bottom-6 rounded-2xl border border-white/10 bg-black/45 px-4 py-3 text-left opacity-0 transition-opacity group-hover:opacity-100">
                  <p className="text-sm font-semibold text-white">Clique para ampliar</p>
                  <p className="mt-1 text-xs text-slate-300">
                    Use esta vista para revisar o raciocinio visual da IA com mais conforto.
                  </p>
                </div>
              </button>
            ) : (
              <div className="max-w-md text-center">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full border border-dashed border-white/10 bg-white/5">
                  <Layers3 className="h-7 w-7 text-slate-300" />
                </div>
                <p className="mt-5 text-lg font-semibold text-white">
                  Esta vista sera preenchida apos a analise
                </p>
                <p className="mt-2 text-sm text-slate-300">
                  A foto original aparece assim que voce selecionar o arquivo. Segmentacao,
                  visualizacao combinada e mapa de atencao chegam junto com o resultado.
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-5">
          <div className="rounded-[24px] border border-white/10 bg-surface-container p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-on-surface">Regiao analisada</p>
                <p className="mt-1 text-xs text-on-surface-variant">
                  Mostra o recorte visual que guiou o pipeline.
                </p>
              </div>
              {detectionImage ? (
                <button
                  type="button"
                  onClick={() => onOpenLightbox(detectionImage, "Regiao analisada")}
                  className="rounded-full border border-white/10 bg-white/5 p-2 text-on-surface transition-colors hover:bg-white/10"
                >
                  <Maximize2 className="h-4 w-4" />
                </button>
              ) : null}
            </div>

            <div className="mt-4 flex min-h-[180px] items-center justify-center overflow-hidden rounded-[18px] border border-white/10 bg-[#08111f]">
              {loading ? (
                <div className="h-[140px] w-[80%] animate-pulse rounded-[18px] bg-white/8" />
              ) : detectionImage ? (
                <img
                  src={detectionImage}
                  alt="Regiao analisada"
                  className="h-full max-h-[220px] w-full object-contain"
                />
              ) : (
                <p className="max-w-[220px] text-center text-sm text-on-surface-variant">
                  O recorte da regiao analisada aparecera aqui apos a execucao.
                </p>
              )}
            </div>
          </div>

          <div className="rounded-[24px] border border-white/10 bg-surface-container p-4">
            <p className="text-sm font-semibold text-on-surface">Legenda de tecidos</p>
            <p className="mt-1 text-xs text-on-surface-variant">
              As cores ajudam a ler a segmentacao e a visualizacao combinada.
            </p>

            <div className="mt-4 space-y-3">
              {tissueLegend.length ? (
                tissueLegend.map((item) => (
                  <div
                    key={item.label}
                    className="rounded-2xl border border-white/10 bg-white/5 px-3 py-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <span
                          className="h-3 w-3 rounded-full"
                          style={{ backgroundColor: item.color }}
                        />
                        <span className="text-sm font-semibold text-on-surface">
                          {item.label}
                        </span>
                      </div>
                      <span className="text-sm font-semibold text-on-surface">
                        {item.value.toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <p className="rounded-2xl border border-dashed border-white/10 px-4 py-5 text-sm text-on-surface-variant">
                  A legenda sera gerada assim que a IA classificar os tecidos visiveis.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
