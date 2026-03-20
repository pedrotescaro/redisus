"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { listPatients } from "@/services/firebase/patient-service";
import { compareEvaluations, listPatientEvaluations } from "@/services/clinical/clinical-api-service";

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

function mapEval(raw: any): Evaluation {
  return {
    id: raw.id,
    date: raw.evaluation_date,
    professional: raw.professional_name ?? "Equipe clínica",
    tissue: {
      granulation: raw.tissue_composition?.granulation ?? 0,
      slough: raw.tissue_composition?.slough ?? 0,
      necrosis: raw.tissue_composition?.necrosis ?? 0,
    },
    areaCm2: raw.wound_area_cm2 ?? 0,
    depthMm: raw.depth_mm ?? 0,
    exudate: "Moderado",
    pain: raw.pain_score ?? 0,
    note: raw.clinical_description ?? "-",
  };
}

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
  const [patientOptions, setPatientOptions] = useState<Array<{ id: string; label: string }>>([]);
  const [patientId, setPatientId] = useState("");
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [leftEvalId, setLeftEvalId] = useState("");
  const [rightEvalId, setRightEvalId] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const patients = await listPatients();
        const options = patients.map((p) => ({ id: p.id, label: `${p.name} (${p.id})` }));
        setPatientOptions(options);
        if (options[0]) setPatientId(options[0].id);
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Falha ao carregar pacientes.";
        setLoadError(message);
      }
    })();
  }, []);

  useEffect(() => {
    if (!patientId) return;
    void (async () => {
      try {
        const data = await listPatientEvaluations(patientId);
        const mapped = data.map(mapEval);
        setEvaluations(mapped);
        setLeftEvalId(mapped[0]?.id ?? "");
        setRightEvalId(mapped[mapped.length - 1]?.id ?? "");
        setLoadError(null);
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Falha ao carregar avaliações.";
        setLoadError(message);
      }
    })();
  }, [patientId]);

  const leftEval = useMemo(
    () => evaluations.find((item) => item.id === leftEvalId) ?? evaluations[0],
    [evaluations, leftEvalId]
  );

  const rightEval = useMemo(
    () =>
      evaluations.find((item) => item.id === rightEvalId) ?? evaluations[evaluations.length - 1],
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
                setPatientId(nextId);
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
      {loadError && (
        <section className="rounded-2xl bg-error/10 text-error p-4 text-sm ghost-border">
          {loadError}
        </section>
      )}

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
              <Button
                variant="secondary"
                onClick={() => {
                  if (!leftEval || !rightEval) return;
                  void compareEvaluations(leftEval.id, rightEval.id);
                }}
              >
                Exportar comparativo
              </Button>
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
