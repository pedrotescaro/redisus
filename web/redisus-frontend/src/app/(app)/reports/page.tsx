"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const patientOptions = [
  { id: "p1", label: "Maria de Souza (ID: 0142)" },
  { id: "p2", label: "João Pereira (ID: 0221)" },
];

const summaryByPatient = {
  p1: {
    diagnosis: "Úlcera venosa de membro inferior direito.",
    baselineDate: "2026-03-04",
    latestDate: "2026-03-18",
    areaReduction: 30.5,
    tissueGain: 29,
    painReduction: 3,
    riskLevel: "Moderado",
    recommendation:
      "Manter desbridamento conservador, controle de exsudato e reavaliação em 7 dias.",
  },
  p2: {
    diagnosis: "Lesão por pressão em calcâneo esquerdo.",
    baselineDate: "2026-03-05",
    latestDate: "2026-03-15",
    areaReduction: 12.9,
    tissueGain: 14,
    painReduction: 2,
    riskLevel: "Alto",
    recommendation:
      "Intensificar alívio de pressão, avaliar necessidade de cobertura antimicrobiana.",
  },
};

export default function ReportsPage() {
  const [patientId, setPatientId] = useState("p1");
  const [reportType, setReportType] = useState("evolucao");
  const [periodStart, setPeriodStart] = useState("2026-03-01");
  const [periodEnd, setPeriodEnd] = useState("2026-03-19");
  const [professional, setProfessional] = useState("Equipe HEAL+");

  const summary = useMemo(() => summaryByPatient[patientId], [patientId]);

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
        </article>

        <aside className="rounded-2xl bg-surface-container p-6 ghost-border">
          <h3 className="text-lg font-bold font-headline text-on-surface">
            Exportação
          </h3>
          <p className="mt-1 text-sm text-on-surface-variant">
            Gere o documento para anexar ao prontuário.
          </p>

          <div className="mt-5 space-y-3">
            <Button className="w-full justify-center">
              <span className="material-symbols-outlined text-base">
                picture_as_pdf
              </span>
              Exportar PDF
            </Button>
            <Button variant="outline" className="w-full justify-center">
              <span className="material-symbols-outlined text-base">
                description
              </span>
              Exportar DOCX
            </Button>
            <Button variant="secondary" className="w-full justify-center">
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
              <strong className="text-on-surface">3</strong>
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
    </div>
  );
}
