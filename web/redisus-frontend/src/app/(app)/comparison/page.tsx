"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";

type Evaluation = {
  id: string;
  date: string;
  professional: string;
  tissue: {
    granulation: number;
    slough: number;
    necrosis: number;
  };
  areaCm2: number;
  depthMm: number;
  exudate: "Baixo" | "Moderado" | "Alto";
  pain: number;
  note: string;
};

const patientOptions = [
  { id: "p1", label: "Maria de Souza (ID: 0142)" },
  { id: "p2", label: "João Pereira (ID: 0221)" },
];

const evaluationsByPatient: Record<string, Evaluation[]> = {
  p1: [
    {
      id: "a1",
      date: "2026-03-04",
      professional: "Enf. Carla Nascimento",
      tissue: { granulation: 42, slough: 46, necrosis: 12 },
      areaCm2: 12.8,
      depthMm: 4.2,
      exudate: "Alto",
      pain: 7,
      note: "Bordas maceradas e exsudato espesso.",
    },
    {
      id: "a2",
      date: "2026-03-11",
      professional: "Enf. Carla Nascimento",
      tissue: { granulation: 58, slough: 34, necrosis: 8 },
      areaCm2: 10.4,
      depthMm: 3.7,
      exudate: "Moderado",
      pain: 5,
      note: "Melhora de leito com redução de tecido desvitalizado.",
    },
    {
      id: "a3",
      date: "2026-03-18",
      professional: "Dr. Paulo Almeida",
      tissue: { granulation: 71, slough: 24, necrosis: 5 },
      areaCm2: 8.9,
      depthMm: 3.1,
      exudate: "Moderado",
      pain: 4,
      note: "Evolução favorável, manter cobertura absorvente.",
    },
  ],
  p2: [
    {
      id: "b1",
      date: "2026-03-05",
      professional: "Enf. Luiza Matos",
      tissue: { granulation: 30, slough: 52, necrosis: 18 },
      areaCm2: 16.2,
      depthMm: 5.2,
      exudate: "Alto",
      pain: 8,
      note: "Ferida extensa em calcâneo, dor intensa ao curativo.",
    },
    {
      id: "b2",
      date: "2026-03-15",
      professional: "Enf. Luiza Matos",
      tissue: { granulation: 44, slough: 43, necrosis: 13 },
      areaCm2: 14.1,
      depthMm: 4.8,
      exudate: "Moderado",
      pain: 6,
      note: "Redução parcial de necrose após desbridamento.",
    },
  ],
};

function getDeltaLabel(value: number, lowerIsBetter = true) {
  if (value === 0) return { text: "Sem variação", tone: "text-outline" };
  const improved = lowerIsBetter ? value < 0 : value > 0;
  if (improved) return { text: "Melhora", tone: "text-primary" };
  return { text: "Piora", tone: "text-tertiary" };
}

function MetricRow({
  label,
  before,
  after,
  suffix = "",
  lowerIsBetter = true,
}: {
  label: string;
  before: number;
  after: number;
  suffix?: string;
  lowerIsBetter?: boolean;
}) {
  const delta = Number((after - before).toFixed(1));
  const deltaLabel = getDeltaLabel(delta, lowerIsBetter);
  const sign = delta > 0 ? "+" : "";

  return (
    <div className="rounded-xl bg-surface-container-low p-4 ghost-border">
      <p className="text-xs uppercase tracking-[0.16em] text-on-surface-variant">
        {label}
      </p>
      <div className="mt-2 flex items-end justify-between">
        <p className="text-sm text-on-surface-variant">
          {before}
          {suffix} {"->"} {after}
          {suffix}
        </p>
        <p className={`text-xs font-semibold ${deltaLabel.tone}`}>
          {sign}
          {delta}
          {suffix} ({deltaLabel.text})
        </p>
      </div>
    </div>
  );
}

export default function ComparisonPage() {
  const [patientId, setPatientId] = useState("p1");
  const [leftEvalId, setLeftEvalId] = useState("a1");
  const [rightEvalId, setRightEvalId] = useState("a3");

  const evaluations = evaluationsByPatient[patientId] ?? [];

  const leftEval = useMemo(
    () => evaluations.find((item) => item.id === leftEvalId) ?? evaluations[0],
    [evaluations, leftEvalId]
  );

  const rightEval = useMemo(
    () =>
      evaluations.find((item) => item.id === rightEvalId) ??
      evaluations[evaluations.length - 1],
    [evaluations, rightEvalId]
  );

  const timelineOptions = evaluations.map((evaluation) => ({
    id: evaluation.id,
    label: new Date(`${evaluation.date}T12:00:00`).toLocaleDateString("pt-BR"),
  }));

  const hasComparison = Boolean(leftEval && rightEval);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-extrabold font-headline text-on-surface">
          Comparar Avaliações
        </h1>
        <p className="text-on-surface-variant mt-1">
          Visualize avaliações lado a lado do mesmo paciente para acompanhar a
          evolução clínica da ferida.
        </p>
      </div>

      <section className="rounded-2xl bg-surface-container p-6 ghost-border shadow-ambient">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-[0.16em] text-on-surface-variant">
              Paciente
            </label>
            <select
              value={patientId}
              onChange={(event) => {
                const nextId = event.target.value;
                const nextEvals = evaluationsByPatient[nextId] ?? [];
                setPatientId(nextId);
                setLeftEvalId(nextEvals[0]?.id ?? "");
                setRightEvalId(nextEvals[nextEvals.length - 1]?.id ?? "");
              }}
              className="h-12 w-full rounded-xl bg-surface-container-high px-4 text-sm text-on-surface ghost-border outline-none focus:border-primary"
            >
              {patientOptions.map((patient) => (
                <option key={patient.id} value={patient.id}>
                  {patient.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-[0.16em] text-on-surface-variant">
              Avaliação inicial
            </label>
            <select
              value={leftEval?.id}
              onChange={(event) => setLeftEvalId(event.target.value)}
              className="h-12 w-full rounded-xl bg-surface-container-high px-4 text-sm text-on-surface ghost-border outline-none focus:border-primary"
            >
              {timelineOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-[0.16em] text-on-surface-variant">
              Avaliação atual
            </label>
            <select
              value={rightEval?.id}
              onChange={(event) => setRightEvalId(event.target.value)}
              className="h-12 w-full rounded-xl bg-surface-container-high px-4 text-sm text-on-surface ghost-border outline-none focus:border-primary"
            >
              {timelineOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      {hasComparison ? (
        <>
          <section className="grid gap-4 xl:grid-cols-2">
            <article className="rounded-2xl bg-surface-container p-6 ghost-border">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold font-headline">Avaliação A</h2>
                <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                  {new Date(`${leftEval.date}T12:00:00`).toLocaleDateString(
                    "pt-BR"
                  )}
                </span>
              </div>
              <p className="mt-2 text-sm text-on-surface-variant">
                Responsável: {leftEval.professional}
              </p>

              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl bg-surface-container-low p-4">
                  <p className="text-xs uppercase tracking-[0.14em] text-on-surface-variant">
                    Área da lesão
                  </p>
                  <p className="mt-1 text-2xl font-bold text-on-surface">
                    {leftEval.areaCm2} cm2
                  </p>
                </div>
                <div className="rounded-xl bg-surface-container-low p-4">
                  <p className="text-xs uppercase tracking-[0.14em] text-on-surface-variant">
                    Profundidade
                  </p>
                  <p className="mt-1 text-2xl font-bold text-on-surface">
                    {leftEval.depthMm} mm
                  </p>
                </div>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl bg-surface-container-low p-3 text-center">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-on-surface-variant">
                    Granulação
                  </p>
                  <p className="mt-1 text-lg font-bold text-primary">
                    {leftEval.tissue.granulation}%
                  </p>
                </div>
                <div className="rounded-xl bg-surface-container-low p-3 text-center">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-on-surface-variant">
                    Esfacelo
                  </p>
                  <p className="mt-1 text-lg font-bold text-tertiary">
                    {leftEval.tissue.slough}%
                  </p>
                </div>
                <div className="rounded-xl bg-surface-container-low p-3 text-center">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-on-surface-variant">
                    Necrose
                  </p>
                  <p className="mt-1 text-lg font-bold text-error">
                    {leftEval.tissue.necrosis}%
                  </p>
                </div>
              </div>

              <p className="mt-5 rounded-xl bg-surface-container-low p-4 text-sm text-on-surface-variant">
                {leftEval.note}
              </p>
            </article>

            <article className="rounded-2xl bg-surface-container p-6 ghost-border">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold font-headline">Avaliação B</h2>
                <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                  {new Date(`${rightEval.date}T12:00:00`).toLocaleDateString(
                    "pt-BR"
                  )}
                </span>
              </div>
              <p className="mt-2 text-sm text-on-surface-variant">
                Responsável: {rightEval.professional}
              </p>

              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl bg-surface-container-low p-4">
                  <p className="text-xs uppercase tracking-[0.14em] text-on-surface-variant">
                    Área da lesão
                  </p>
                  <p className="mt-1 text-2xl font-bold text-on-surface">
                    {rightEval.areaCm2} cm2
                  </p>
                </div>
                <div className="rounded-xl bg-surface-container-low p-4">
                  <p className="text-xs uppercase tracking-[0.14em] text-on-surface-variant">
                    Profundidade
                  </p>
                  <p className="mt-1 text-2xl font-bold text-on-surface">
                    {rightEval.depthMm} mm
                  </p>
                </div>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl bg-surface-container-low p-3 text-center">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-on-surface-variant">
                    Granulação
                  </p>
                  <p className="mt-1 text-lg font-bold text-primary">
                    {rightEval.tissue.granulation}%
                  </p>
                </div>
                <div className="rounded-xl bg-surface-container-low p-3 text-center">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-on-surface-variant">
                    Esfacelo
                  </p>
                  <p className="mt-1 text-lg font-bold text-tertiary">
                    {rightEval.tissue.slough}%
                  </p>
                </div>
                <div className="rounded-xl bg-surface-container-low p-3 text-center">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-on-surface-variant">
                    Necrose
                  </p>
                  <p className="mt-1 text-lg font-bold text-error">
                    {rightEval.tissue.necrosis}%
                  </p>
                </div>
              </div>

              <p className="mt-5 rounded-xl bg-surface-container-low p-4 text-sm text-on-surface-variant">
                {rightEval.note}
              </p>
            </article>
          </section>

          <section className="rounded-2xl bg-surface-container p-6 ghost-border shadow-ambient">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-xl font-bold font-headline">Resumo de diferenças</h3>
              <Button variant="secondary">Exportar comparativo</Button>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <MetricRow
                label="Área da lesão"
                before={leftEval.areaCm2}
                after={rightEval.areaCm2}
                suffix=" cm2"
              />
              <MetricRow
                label="Profundidade"
                before={leftEval.depthMm}
                after={rightEval.depthMm}
                suffix=" mm"
              />
              <MetricRow
                label="Dor referida"
                before={leftEval.pain}
                after={rightEval.pain}
              />
              <MetricRow
                label="Granulação"
                before={leftEval.tissue.granulation}
                after={rightEval.tissue.granulation}
                suffix="%"
                lowerIsBetter={false}
              />
            </div>

            <div className="mt-4 rounded-xl bg-surface-container-low p-4 text-sm text-on-surface-variant">
              Exsudato: <strong className="text-on-surface">{leftEval.exudate}</strong>{" "}
              {"->"} <strong className="text-on-surface">{rightEval.exudate}</strong>
            </div>
          </section>
        </>
      ) : (
        <section className="rounded-2xl bg-surface-container p-8 text-center ghost-border">
          <p className="text-on-surface-variant">
            Não há avaliações suficientes para comparação deste paciente.
          </p>
        </section>
      )}
    </div>
  );
}
