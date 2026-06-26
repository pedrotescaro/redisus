import { ArrowDown, ArrowRight, ArrowUp, Camera, Image as ImageIcon, LineChart, TrendingDown, TrendingUp } from 'lucide-react';

import { buildEvolutionText } from '../../features/reports/reportService';
import { formatDate } from '../../lib/date';
import { estimateRoisAreaPercent } from '../../lib/roi';
import type { Evaluation, Patient } from '../../lib/types';
import { RoiImageOverlay } from '../roi/RoiImageOverlay';
import { Badge } from '../ui/Badge';
import { Card } from '../ui/Card';

interface ComparisonViewProps {
  patient: Patient;
  evaluationA: Evaluation;
  evaluationB: Evaluation;
  allEvaluations?: Evaluation[];
}

export function ComparisonView({ patient, evaluationA, evaluationB, allEvaluations = [] }: ComparisonViewProps) {
  const areaA = estimateRoisAreaPercent(evaluationA.images[0]?.rois || []);
  const areaB = estimateRoisAreaPercent(evaluationB.images[0]?.rois || []);
  const areaDelta = areaA && areaB ? areaB - areaA : null;
  const painDelta = evaluationB.painLevel - evaluationA.painLevel;
  const sequence = allEvaluations.length ? allEvaluations : [evaluationA, evaluationB];

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-heal-teal">Comparativo clínico</p>
            <h2 className="mt-1 text-2xl font-black text-heal-ink dark:text-white">{patient.name}</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-heal-muted dark:text-zinc-400">{buildEvolutionText(evaluationA, evaluationB)}</p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:min-w-[260px]">
            <DeltaPill label="Dor" value={formatDelta(painDelta, ' ponto')} trend={painDelta} />
            <DeltaPill label="Área" value={areaDelta === null ? 'sem ROI' : formatDelta(areaDelta, '%')} trend={areaDelta || 0} />
          </div>
        </div>

        <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_auto_1fr] lg:items-stretch">
          <CompareCard title="Antes" evaluation={evaluationA} area={areaA} />
          <ProgressBridge areaA={areaA} areaB={areaB} painDelta={painDelta} />
          <CompareCard title="Agora" evaluation={evaluationB} area={areaB} />
        </div>
      </Card>

      <section className="grid gap-6 xl:grid-cols-[1fr_420px] min-w-0">
        <Card className="min-w-0">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue dark:bg-blue-950/40">
              <LineChart className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs font-black uppercase tracking-[0.18em] text-heal-teal">Sequencia</p>
              <h3 className="text-lg font-black text-heal-ink dark:text-white">Área visual estimada</h3>
            </div>
          </div>
          <div className="mt-5 flex h-44 items-end gap-3 overflow-x-auto rounded-2xl bg-heal-canvas p-4 dark:bg-zinc-950">
            {sequence.map(evaluation => {
              const area = estimateRoisAreaPercent(evaluation.images[0]?.rois || []);
              const height = area ? Math.max(14, Math.min(100, area)) : 8;
              const selected = evaluation.id === evaluationA.id || evaluation.id === evaluationB.id;
              return (
                <div key={evaluation.id} className="flex min-w-20 flex-1 flex-col items-center justify-end gap-2">
                  <div className={`w-full rounded-t-2xl ${selected ? 'bg-heal-blue' : 'bg-heal-teal'}`} style={{ height: `${height}%` }} />
                  <p className="text-center text-[11px] font-black text-heal-muted dark:text-zinc-400">{formatDate(evaluation.date)}</p>
                </div>
              );
            })}
          </div>
        </Card>

        <Card>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-heal-teal">TIMERS</p>
          <h3 className="mt-1 text-lg font-black text-heal-ink dark:text-white">Comparativo clínico</h3>
          <div className="mt-4 space-y-3">
            <ClinicalRow label="T" title="Tecido" before={evaluationA.timers.tissue} after={evaluationB.timers.tissue} />
            <ClinicalRow label="I" title="Inflamação / infecção" before={evaluationA.timers.infection} after={evaluationB.timers.infection} />
            <ClinicalRow label="M" title="Umidade" before={evaluationA.timers.moisture} after={evaluationB.timers.moisture} />
            <ClinicalRow label="E" title="Bordas" before={evaluationA.timers.edge} after={evaluationB.timers.edge} />
          </div>
        </Card>
      </section>
    </div>
  );
}

function CompareCard({ title, evaluation, area }: { title: string; evaluation: Evaluation; area: number }) {
  const image = evaluation.images[0];

  return (
    <article className="rounded-2xl border border-heal-line bg-heal-canvas p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge tone={title === 'Antes' ? 'amber' : 'blue'}>{title}</Badge>
        <Badge tone="slate">{formatDate(evaluation.date)}</Badge>
        <Badge tone={evaluation.painLevel >= 7 ? 'red' : evaluation.painLevel >= 4 ? 'amber' : 'green'}>Dor {evaluation.painLevel}/10</Badge>
      </div>
      <div className="relative aspect-[4/3] overflow-hidden rounded-2xl bg-slate-950">
        {image ? (
          <>
            <img src={image.downloadURL} alt="" className="h-full w-full object-contain" />
            <RoiImageOverlay rois={image.rois} />
          </>
        ) : (
          <div className="flex h-full items-center justify-center text-sm font-semibold text-heal-muted">
            <ImageIcon className="mr-2 h-5 w-5" />
            Sem imagem
          </div>
        )}
      </div>
      <dl className="mt-4 grid gap-2 text-sm">
        <InfoRow label="Local" value={evaluation.woundLocation} />
        <InfoRow label="Exsudato" value={`${evaluation.exudateAmount} - ${evaluation.exudateType}`} />
        <InfoRow label="Area ROI" value={area ? `${area.toFixed(1)}% da imagem` : 'Sem ROI suficiente'} />
      </dl>
    </article>
  );
}

function ProgressBridge({ areaA, areaB, painDelta }: { areaA: number; areaB: number; painDelta: number }) {
  const trend = areaA && areaB ? areaB - areaA : painDelta;
  const TrendIcon = trend < 0 ? TrendingDown : trend > 0 ? TrendingUp : ArrowRight;

  return (
    <div className="flex items-center justify-center lg:w-24">
      <div className="flex w-full flex-row items-center gap-3 lg:flex-col">
        <Camera className="h-5 w-5 text-heal-muted" />
        <div className="h-1 flex-1 rounded-full bg-heal-line dark:bg-zinc-800 lg:h-24 lg:w-1 lg:flex-none">
          <div className={`h-full rounded-full ${trend <= 0 ? 'bg-heal-teal' : 'bg-heal-warning'} lg:w-full`} />
        </div>
        <div className={`flex h-10 w-10 items-center justify-center rounded-full ${trend <= 0 ? 'bg-emerald-50 text-heal-teal dark:bg-emerald-950/40' : 'bg-amber-50 text-heal-warning dark:bg-amber-950/40'}`}>
          <TrendIcon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

function ClinicalRow({ label, title, before, after }: { label: string; title: string; before: string; after: string }) {
  const changed = summarize(before) !== summarize(after);
  return (
    <div className="rounded-2xl border border-heal-line bg-heal-canvas p-3 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-heal-softBlue text-sm font-black text-heal-blue dark:bg-blue-950/40">{label}</span>
          <p className="text-sm font-black text-heal-ink dark:text-white">{title}</p>
        </div>
        {changed ? <ArrowRight className="h-4 w-4 text-heal-blue" /> : <span className="text-xs font-black text-heal-muted">Estável</span>}
      </div>
      <p className="text-xs leading-5 text-heal-muted dark:text-zinc-400">
        <strong>Antes:</strong> {summarize(before)}
      </p>
      <p className="mt-1 text-xs leading-5 text-heal-muted dark:text-zinc-400">
        <strong>Agora:</strong> {summarize(after)}
      </p>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[88px_1fr] gap-3">
      <dt className="font-semibold text-heal-muted dark:text-zinc-400">{label}</dt>
      <dd className="font-bold text-heal-ink dark:text-white">{value}</dd>
    </div>
  );
}

function DeltaPill({ label, value, trend }: { label: string; value: string; trend: number }) {
  const Icon = trend < 0 ? ArrowDown : trend > 0 ? ArrowUp : ArrowRight;
  const tone = trend < 0 ? 'bg-emerald-50 text-heal-teal dark:bg-emerald-950/40' : trend > 0 ? 'bg-amber-50 text-heal-warning dark:bg-amber-950/40' : 'bg-slate-100 text-slate-600 dark:bg-zinc-800 dark:text-zinc-300';
  return (
    <div className={`rounded-2xl px-3 py-2 ${tone}`}>
      <p className="text-[11px] font-black uppercase tracking-[0.12em]">{label}</p>
      <p className="mt-1 inline-flex items-center gap-1 text-sm font-black">
        <Icon className="h-4 w-4" />
        {value}
      </p>
    </div>
  );
}

function formatDelta(value: number, suffix: string) {
  if (value === 0) return 'estável';
  const formatted = Math.abs(value).toFixed(suffix === '%' ? 1 : 0);
  if (suffix === '%') return `${value > 0 ? '+' : '-'}${formatted}%`;
  return `${value > 0 ? '+' : '-'}${formatted}${suffix}${formatted === '1' ? '' : 's'}`;
}

function summarize(value: string) {
  if (!value) return 'Não informado';
  const firstParts = value
    .split('|')
    .map(item => item.trim())
    .filter(Boolean)
    .slice(0, 2)
    .join(' | ');
  return firstParts || 'Não informado';
}
