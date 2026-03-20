"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { listPatients } from "@/services/firebase/patient-service";
import {
  generateReport,
  getReportDownloadUrl,
  listPatientEvaluations,
} from "@/services/clinical/clinical-api-service";

type EvaluationSummary = {
  diagnosis: string;
  baselineDate: string;
  latestDate: string;
  areaReduction: number;
  tissueGain: number;
  painReduction: number;
  riskLevel: string;
  recommendation: string;
  evaluationCount: number;
};

const EMPTY_SUMMARY: EvaluationSummary = {
  diagnosis: "Selecione um paciente com avaliações para gerar o resumo.",
  baselineDate: "-",
  latestDate: "-",
  areaReduction: 0,
  tissueGain: 0,
  painReduction: 0,
  riskLevel: "Não calculado",
  recommendation: "Gere o relatório para obter recomendações clínicas estruturadas.",
  evaluationCount: 0,
};

function computeSummary(evaluations: Array<Record<string, any>>): EvaluationSummary {
  if (evaluations.length === 0) return EMPTY_SUMMARY;

  const sorted = [...evaluations].sort(
    (a, b) =>
      new Date(a.evaluation_date ?? "").getTime() -
      new Date(b.evaluation_date ?? "").getTime(),
  );

  const first = sorted[0];
  const last = sorted[sorted.length - 1];

  const firstArea = Number(first.wound_area_cm2 ?? 0);
  const lastArea = Number(last.wound_area_cm2 ?? 0);
  const areaReduction =
    firstArea > 0
      ? Number((((firstArea - lastArea) / firstArea) * 100).toFixed(1))
      : 0;

  const firstGranulation = Number(first.tissue_composition?.granulation ?? 0);
  const lastGranulation = Number(last.tissue_composition?.granulation ?? 0);
  const tissueGain = Number((lastGranulation - firstGranulation).toFixed(1));

  const firstPain = Number(first.pain_score ?? 0);
  const lastPain = Number(last.pain_score ?? 0);
  const painReduction = Number((firstPain - lastPain).toFixed(1));

  const bradenScore = Number(last.braden_score ?? 0);
  let riskLevel = "Não calculado";
  if (bradenScore > 0) {
    if (bradenScore <= 9) riskLevel = "Muito alto";
    else if (bradenScore <= 12) riskLevel = "Alto";
    else if (bradenScore <= 14) riskLevel = "Moderado";
    else if (bradenScore <= 18) riskLevel = "Baixo";
    else riskLevel = "Sem risco";
  }

  const diagnosis =
    last.clinical_description ||
    `${last.wound_type ?? "Ferida"} em acompanhamento clínico.`;

  const recommendation =
    areaReduction > 20
      ? "Boa evolução clínica. Manter conduta atual e reavaliar conforme protocolo."
      : areaReduction > 0
        ? "Evolução lenta. Considerar ajuste de cobertura e reavaliação em 7 dias."
        : "Sem melhora significativa. Avaliar necessidade de intervenção adicional.";

  return {
    diagnosis,
    baselineDate: first.evaluation_date ?? "-",
    latestDate: last.evaluation_date ?? "-",
    areaReduction,
    tissueGain,
    painReduction,
    riskLevel,
    recommendation,
    evaluationCount: sorted.length,
  };
}

export default function ReportsPage() {
  const [patientOptions, setPatientOptions] = useState<Array<{ id: string; label: string }>>([]);
  const [patientId, setPatientId] = useState("");
  const [reportType, setReportType] = useState("evolucao");
  const [periodStart, setPeriodStart] = useState(() => {
    const d = new Date();
    d.setMonth(d.getMonth() - 1);
    return d.toISOString().split("T")[0];
  });
  const [periodEnd, setPeriodEnd] = useState(() => new Date().toISOString().split("T")[0]);
  const [professional, setProfessional] = useState("Equipe HEAL+");

  const [reportId, setReportId] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [summary, setSummary] = useState<EvaluationSummary>(EMPTY_SUMMARY);
  const [loadingSummary, setLoadingSummary] = useState(false);

  // Load patients from Firestore
  useEffect(() => {
    void (async () => {
      try {
        const patients = await listPatients();
        const options = patients.map((p) => ({ id: p.id, label: `${p.name} (${p.id})` }));
        if (options.length) {
          setPatientOptions(options);
          setPatientId(options[0].id);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "Falha ao carregar pacientes.";
        setApiError(message);
      }
    })();
  }, []);

  // Load evaluations for selected patient and compute summary
  useEffect(() => {
    if (!patientId) return;
    let active = true;
    setLoadingSummary(true);
    void (async () => {
      try {
        const evaluations = await listPatientEvaluations(patientId);
        if (!active) return;
        setSummary(computeSummary(evaluations));
        setApiError(null);
      } catch {
        if (active) setSummary(EMPTY_SUMMARY);
      } finally {
        if (active) setLoadingSummary(false);
      }
    })();
    return () => { active = false; };
  }, [patientId]);

  const handleGenerate = async () => {
    try {
      const generated = await generateReport({
        patient_id: patientId,
        report_type: reportType,
        period_start: periodStart,
        period_end: periodEnd,
        professional,
      });
      setReportId(generated.reportId);
      setApiError(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Falha ao gerar relatório.";
      setApiError(message);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-extrabold font-headline text-on-surface">
          Gerar Relatório
        </h1>
        <p className="text-on-surface-variant mt-1">
          Monte um relatório clínico com indicadores de evolução, achados e
          recomendações para prontuário.
        </p>
      </div>

      <section className="rounded-2xl bg-surface-container p-6 ghost-border shadow-ambient">
        <h2 className="text-lg font-bold font-headline text-on-surface">
          Parâmetros do relatório
        </h2>

        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-[0.16em] text-on-surface-variant">
              Paciente
            </label>
            <select
              value={patientId}
              onChange={(event) => setPatientId(event.target.value)}
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
              Tipo
            </label>
            <select
              value={reportType}
              onChange={(event) => setReportType(event.target.value)}
              className="h-12 w-full rounded-xl bg-surface-container-high px-4 text-sm text-on-surface ghost-border outline-none focus:border-primary"
            >
              <option value="evolucao">Evolução clínica</option>
              <option value="alta">Resumo para alta</option>
              <option value="tecnico">Relatório técnico</option>
            </select>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-[0.16em] text-on-surface-variant">
              Início
            </label>
            <Input
              type="date"
              value={periodStart}
              onChange={(event) => setPeriodStart(event.target.value)}
              className="h-12"
            />
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold uppercase tracking-[0.16em] text-on-surface-variant">
              Fim
            </label>
            <Input
              type="date"
              value={periodEnd}
              onChange={(event) => setPeriodEnd(event.target.value)}
              className="h-12"
            />
          </div>
        </div>

        <div className="mt-4 max-w-md space-y-2">
          <label className="text-xs font-bold uppercase tracking-[0.16em] text-on-surface-variant">
            Responsável pelo documento
          </label>
          <Input
            value={professional}
            onChange={(event) => setProfessional(event.target.value)}
            placeholder="Nome do profissional ou equipe"
          />
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[2fr_1fr]">
        <article className="rounded-2xl bg-surface-container p-6 ghost-border shadow-ambient">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-primary">
                Pré-visualização
              </p>
              <h2 className="mt-1 text-2xl font-extrabold font-headline text-on-surface">
                Relatório de evolução de ferida
              </h2>
              <p className="mt-2 text-sm text-on-surface-variant">
                Período:{" "}
                {new Date(`${periodStart}T12:00:00`).toLocaleDateString("pt-BR")}{" "}
                até {new Date(`${periodEnd}T12:00:00`).toLocaleDateString("pt-BR")}
              </p>
            </div>
            <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
              {reportType.toUpperCase()}
            </span>
          </div>

          {loadingSummary ? (
            <div className="mt-5 rounded-xl bg-surface-container-low p-4 text-sm text-on-surface-variant">
              Carregando dados das avaliações...
            </div>
          ) : (
            <>
              <div className="mt-5 rounded-xl bg-surface-container-low p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-on-surface-variant">
                  Diagnóstico principal
                </p>
                <p className="mt-2 text-sm text-on-surface">{summary.diagnosis}</p>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <div className="rounded-xl bg-surface-container-low p-4">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-on-surface-variant">
                    Redução de área
                  </p>
                  <p className="mt-2 text-2xl font-bold text-primary">
                    {summary.areaReduction}%
                  </p>
                </div>
                <div className="rounded-xl bg-surface-container-low p-4">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-on-surface-variant">
                    Ganho de granulação
                  </p>
                  <p className="mt-2 text-2xl font-bold text-primary">
                    +{summary.tissueGain}%
                  </p>
                </div>
                <div className="rounded-xl bg-surface-container-low p-4">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-on-surface-variant">
                    Redução de dor
                  </p>
                  <p className="mt-2 text-2xl font-bold text-primary">
                    -{summary.painReduction}
                  </p>
                </div>
              </div>

              <div className="mt-4 rounded-xl bg-surface-container-low p-4 text-sm text-on-surface-variant">
                <p className="mb-2 text-xs font-bold uppercase tracking-[0.16em]">
                  Conduta recomendada
                </p>
                {summary.recommendation}
              </div>
            </>
          )}
        </article>

        <aside className="rounded-2xl bg-surface-container p-6 ghost-border">
          <h3 className="text-lg font-bold font-headline text-on-surface">
            Exportação
          </h3>
          <p className="mt-1 text-sm text-on-surface-variant">
            Gere o documento para anexar ao prontuário.
          </p>

          <div className="mt-5 space-y-3">
            <Button className="w-full justify-center" onClick={() => void handleGenerate()}>
              <span className="material-symbols-outlined text-base">
                picture_as_pdf
              </span>
              Exportar PDF
            </Button>
            <Button
              variant="outline"
              className="w-full justify-center"
              onClick={() => {
                if (!reportId) return;
                window.open(getReportDownloadUrl(reportId, "docx"), "_blank");
              }}
            >
              <span className="material-symbols-outlined text-base">
                description
              </span>
              Exportar DOCX
            </Button>
            <Button
              variant="secondary"
              className="w-full justify-center"
              onClick={() => {
                if (!reportId) return;
                window.open(getReportDownloadUrl(reportId, "pdf"), "_blank");
              }}
            >
              <span className="material-symbols-outlined text-base">mail</span>
              Enviar para equipe
            </Button>
          </div>

          <div className="mt-6 rounded-xl bg-surface-container-low p-4 text-sm text-on-surface-variant">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-on-surface">
              Metadados
            </p>
            <p className="mt-2">
              Avaliações analisadas:{" "}
              <strong className="text-on-surface">{summary.evaluationCount}</strong>
            </p>
            <p>
              Janela temporal:{" "}
              <strong className="text-on-surface">
                {summary.baselineDate} a {summary.latestDate}
              </strong>
            </p>
            <p>
              Risco atual:{" "}
              <strong className="text-on-surface">{summary.riskLevel}</strong>
            </p>
            <p>
              Assinatura:{" "}
              <strong className="text-on-surface">{professional}</strong>
            </p>
          </div>
        </aside>
      </section>
      {apiError && (
        <section className="rounded-2xl bg-error/10 text-error p-4 text-sm ghost-border">
          {apiError}
        </section>
      )}
    </div>
  );
}
