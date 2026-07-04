import { useState } from 'react';
import { User, Sparkles, Loader2, BrainCircuit, AlertTriangle } from 'lucide-react';
import { RoiImageOverlay } from '../roi/RoiImageOverlay';
import { Badge } from '../ui/Badge';
import { Card } from '../ui/Card';
import { MarkdownRenderer } from '../ui/MarkdownRenderer';
import { CLINICAL_DISCLAIMER } from '../../lib/constants';
import { formatDateLong } from '../../lib/date';
import type { Evaluation, Patient, UserProfile } from '../../lib/types';

interface ReportPreviewProps {
  patient: Patient;
  evaluation: Evaluation;
  profile: UserProfile | null;
  analysis: string | null;
  loadingAnalysis: boolean;
  analysisError: string | null;
  onGenerateAnalysis: () => void;
  includeAi: boolean;
}

export function ReportPreview({
  patient,
  evaluation,
  profile,
  analysis,
  loadingAnalysis,
  analysisError,
  onGenerateAnalysis,
  includeAi
}: ReportPreviewProps) {
  const image = evaluation.images[0];

  return (
    <Card className="print:border-0 print:shadow-none p-6">
      {/* Header section */}
      <div className="flex flex-col justify-between gap-4 border-b border-heal-line pb-5 dark:border-zinc-800 sm:flex-row sm:items-center">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue shadow-sm ring-1 ring-heal-line/30 dark:bg-blue-950/40">
            <User className="h-7 w-7" />
          </div>
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-heal-muted dark:text-zinc-500">Relatório clínico Heal+</p>
            <h3 className="mt-1 text-2xl font-black text-heal-ink dark:text-white">{patient.name}</h3>
            <p className="text-base font-semibold text-slate-650 dark:text-zinc-400">{formatDateLong(evaluation.date)}</p>
          </div>
        </div>
        <Badge tone="blue">Registro profissional</Badge>
      </div>

      {/* 1. Patient Demographics Sub-Card */}
      <div className="mt-5 rounded-2xl border border-heal-line/60 bg-slate-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-900/30">
        <p className="text-xs font-bold uppercase tracking-wider text-heal-muted dark:text-zinc-500 mb-3">Identificação do Paciente</p>
        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4">
          <InfoCompact label="Paciente" value={patient.name} />
          <InfoCompact label="Telefone" value={patient.phone} />
          <InfoCompact label="E-mail" value={patient.email || 'Não informado'} />
          <InfoCompact label="Nascimento" value={patient.birthDate} />
        </div>
      </div>

      {/* 2. Main content: Assessment & Image */}
      <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        {/* Left column: assessment details */}
        <div className="space-y-4">
          <div className="rounded-2xl border border-heal-line/60 p-4 dark:border-zinc-800 bg-white dark:bg-zinc-950/40">
            <p className="text-xs font-bold uppercase tracking-wider text-heal-muted dark:text-zinc-500 mb-3">Parâmetros da Lesão</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Info label="Localização" value={evaluation.woundLocation} />
              <Info label="Etiologia" value={evaluation.woundEtiology} />
              <Info label="Nível de Dor" value={`${evaluation.painLevel}/10`} />
              <Info label="Exsudato" value={`${evaluation.exudateAmount} · ${evaluation.exudateType}`} />
              <Info label="Bordas" value={evaluation.borderCharacteristics} />
              <Info label="Pele perilesional" value={evaluation.periwoundSkin} />
            </div>
          </div>
        </div>

        {/* Right column: Image */}
        <div className="flex flex-col justify-between">
          <div className="relative aspect-[4/3] w-full overflow-hidden rounded-2xl bg-slate-950 shadow-md">
            {image ? (
              <>
                <img src={image.downloadURL} alt="Imagem da ferida" className="h-full w-full object-contain" />
                <RoiImageOverlay rois={image.rois} />
              </>
            ) : (
              <div className="flex h-full items-center justify-center text-sm font-semibold text-slate-400">Sem imagem vinculada</div>
            )}
          </div>
          {image?.rois.length ? (
            <div className="mt-3 text-center">
              <p className="text-xs font-bold text-heal-muted dark:text-zinc-500">
                Regiões demarcadas: {image.rois.map(r => r.label).join(', ')}
              </p>
            </div>
          ) : null}
        </div>
      </div>

      {/* 3. T.I.M.E.R.S. section */}
      <div className="mt-8">
        <p className="text-xs font-bold uppercase tracking-wider text-heal-muted dark:text-zinc-500 mb-4">Framework T.I.M.E.R.S.</p>
        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
          {Object.entries(evaluation.timers).map(([key, value]) => (
            <div key={key} className="rounded-xl border border-heal-line/60 bg-slate-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-900/30 flex flex-col justify-between">
              <div>
                <p className="text-xs font-black uppercase tracking-wide text-heal-blue">{key}</p>
                {renderTimerContent(value)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Notes section if any */}
      {evaluation.notes ? (
        <div className="mt-6 rounded-xl bg-slate-50 p-4 dark:bg-zinc-900/50 border border-heal-line dark:border-zinc-800">
          <p className="text-sm font-bold text-heal-ink dark:text-white">Observações</p>
          <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-zinc-300">{evaluation.notes}</p>
        </div>
      ) : null}

      {/* AI Analysis Section */}
      {includeAi && (
        analysis ? (
          <div className="mt-8 border-t border-heal-line pt-6 dark:border-zinc-800">
            <div className="rounded-2xl border border-heal-blue/20 bg-heal-softBlue/10 p-5 dark:border-blue-500/20 dark:bg-blue-950/20">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-heal-softBlue text-heal-blue dark:bg-blue-950/40">
                  <BrainCircuit className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-xs font-black uppercase tracking-wide text-heal-blue">Análise de IA Generativa</p>
                  <h4 className="text-sm font-bold text-heal-ink dark:text-white">Parecer Clínico Automatizado</h4>
                </div>
              </div>

              <div className="mt-4">
                <div className="text-sm leading-relaxed text-slate-700 dark:text-zinc-300">
                  <MarkdownRenderer text={analysis} />
                </div>
                <div className="mt-4 flex items-center justify-between gap-3 border-t border-heal-line/40 dark:border-zinc-800/40 pt-4 no-print">
                  <p className="text-[11px] text-heal-muted dark:text-zinc-500 font-medium">
                    Aviso: Esta análise é gerada por inteligência artificial para apoio clínico e deve ser validada por um profissional de saúde.
                  </p>
                  <button
                    onClick={onGenerateAnalysis}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-heal-blue/20 bg-white dark:bg-zinc-900 text-xs font-bold text-heal-blue cursor-pointer hover:bg-heal-softBlue/30 transition-colors"
                  >
                    <Sparkles className="h-3 w-3" />
                    Regerar
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="mt-8 border-t border-heal-line pt-6 dark:border-zinc-800 no-print">
            <div className="rounded-2xl border border-heal-blue/20 bg-heal-softBlue/10 p-5 dark:border-blue-500/20 dark:bg-blue-950/20">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-heal-softBlue text-heal-blue dark:bg-blue-950/40">
                  <BrainCircuit className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-xs font-black uppercase tracking-wide text-heal-blue">Análise de IA Generativa</p>
                  <h4 className="text-sm font-bold text-heal-ink dark:text-white">Parecer Clínico Automatizado</h4>
                </div>
              </div>
              <div className="mt-4 flex flex-col items-center py-4 text-center">
                {loadingAnalysis ? (
                  <div className="flex flex-col items-center gap-2">
                    <Loader2 className="h-6 w-6 animate-spin text-heal-blue" />
                    <p className="text-xs font-semibold text-heal-muted dark:text-zinc-400">Analisando parâmetros clínicos da ferida...</p>
                  </div>
                ) : (
                  <>
                    <p className="text-xs text-heal-muted dark:text-zinc-400 mb-4 max-w-md">
                      Gere uma análise completa contendo resumo clínico, pontos de atenção e conduta baseada no framework T.I.M.E.R.S. usando inteligência artificial.
                    </p>
                    <button
                      onClick={onGenerateAnalysis}
                      className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-heal-blue hover:bg-heal-blueDark text-white text-xs font-bold shadow-md cursor-pointer transition-all hover:scale-[1.02] active:scale-[0.98]"
                    >
                      <Sparkles className="h-4 w-4" />
                      Gerar Análise por IA
                    </button>
                  </>
                )}

                {analysisError && (
                  <div className="mt-3 flex items-center gap-2 text-xs font-semibold text-red-500 bg-red-500/10 px-3 py-2 rounded-lg border border-red-500/20">
                    <AlertTriangle className="h-4 w-4" />
                    <span>{analysisError}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )
      )}

      {/* Signatures */}
      <div className="mt-8 border-t border-heal-line pt-4 text-sm text-slate-500 dark:border-zinc-800 dark:text-zinc-400">
        <div className="flex flex-col gap-2">
          {evaluation.signature && (
            <div className="mb-2">
              <p className="text-xs font-semibold mb-1 text-slate-400 dark:text-zinc-500">Assinatura digitalizada:</p>
              <img src={evaluation.signature} alt="Assinatura" className="h-12 w-auto border border-heal-line dark:border-zinc-800 rounded bg-white p-1 object-contain max-w-[200px]" />
            </div>
          )}
          <p>{profile?.displayName ? `Assinatura: ${profile.displayName}` : 'Assinatura: profissional não informado'}</p>
        </div>
        <p className="mt-4 font-bold text-heal-blue">Cuidado inteligente. Evolução visível.</p>
        <p className="mt-2">{CLINICAL_DISCLAIMER}</p>
      </div>
    </Card>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 dark:bg-zinc-950">
      <span className="text-sm font-semibold text-slate-500 dark:text-zinc-400">{label}</span>
      <span className="text-right text-sm font-bold text-heal-ink dark:text-white">{value}</span>
    </div>
  );
}

function InfoCompact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] font-semibold text-slate-400 dark:text-zinc-500 uppercase tracking-wider">{label}</span>
      <span className="text-sm font-bold text-heal-ink dark:text-white truncate" title={value}>{value}</span>
    </div>
  );
}

function renderTimerContent(value: string) {
  if (!value) return <p className="text-sm text-slate-400 dark:text-zinc-500 mt-2">Não informado</p>;
  
  const parts = value.split('|').map(p => p.trim()).filter(Boolean);
  if (parts.length === 0) return <p className="text-sm text-slate-400 dark:text-zinc-500 mt-2">Não informado</p>;

  return (
    <div className="mt-2 space-y-1.5">
      {parts.map((part, idx) => {
        const colonIndex = part.indexOf(':');
        if (colonIndex > -1) {
          const label = part.substring(0, colonIndex).trim();
          const val = part.substring(colonIndex + 1).trim();
          
          const isMultiValue = val.includes(',') && (val.includes('%') || val.includes('cm') || val.length > 25);
          if (isMultiValue) {
            const subParts = val.split(',').map(s => s.trim()).filter(Boolean);
            return (
              <div key={idx} className="flex flex-col gap-1.5 border-b border-slate-100 dark:border-zinc-800/80 pb-2 pt-1 last:border-0 last:pb-0">
                <span className="font-medium text-slate-400 dark:text-zinc-500">{label}</span>
                <div className="pl-2.5 space-y-1 border-l-2 border-slate-100 dark:border-zinc-800/80">
                  {subParts.map((sp, sIdx) => {
                    const match = sp.match(/^(.*?)\s+(\d+%)$/);
                    if (match) {
                      return (
                        <div key={sIdx} className="flex justify-between text-[11px] text-slate-700 dark:text-zinc-350">
                          <span className="font-medium text-slate-400 dark:text-zinc-500">{match[1]}</span>
                          <span className="font-bold text-slate-800 dark:text-zinc-200">{match[2]}</span>
                        </div>
                      );
                    }
                    return (
                      <div key={sIdx} className="text-[11px] font-semibold text-slate-800 dark:text-zinc-200">
                        {sp}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          }

          return (
            <div key={idx} className="flex justify-between text-xs border-b border-slate-100 dark:border-zinc-800 pb-1 last:border-0 last:pb-0">
              <span className="font-medium text-slate-400 dark:text-zinc-500">{label}</span>
              <span className="font-semibold text-slate-800 dark:text-zinc-200">{val}</span>
            </div>
          );
        }
        return (
          <div key={idx} className="text-xs font-semibold text-slate-700 dark:text-zinc-300">
            {part}
          </div>
        );
      })}
    </div>
  );
}
