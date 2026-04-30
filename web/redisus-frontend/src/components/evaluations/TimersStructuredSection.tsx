import { Activity, Droplets, Flame, RefreshCw, ShieldCheck, UsersRound } from 'lucide-react';
import type { Dispatch, ReactNode, SetStateAction } from 'react';
import type { FieldErrors, UseFormRegister, UseFormSetValue, UseFormWatch } from 'react-hook-form';

import { FORM_OPTIONS } from '../../lib/constants';
import { Card } from '../ui/Card';
import { Input } from '../ui/Input';
import { Select } from '../ui/Select';
import { Textarea } from '../ui/Textarea';
import type { EvaluationFormValues } from '../../features/evaluations/evaluationSchema';

export interface TimersDraft {
  width: string;
  length: string;
  depth: string;
  evolutionTime: string;
  granulation: string;
  epithelialization: string;
  slough: string;
  dryNecrosis: string;
  painFactors: string;
  cultureDone: boolean;
  cultureResult: string;
  exudateConsistency: string;
  edgeFixation: string;
  healingSpeed: string;
  hasTunnel: boolean;
  tunnelLocation: string;
  periwoundMoisture: string;
  periwoundExtent: string;
  periwoundConditions: string[];
  treatmentPlan: string;
  followUpDate: string;
  responsibleProfessional: string;
  registry: string;
  activityLevel: string;
  adherence: string;
  socialSupport: string;
  physicalActivity: boolean;
  activityDescription: string;
  alcoholUse: boolean;
  alcoholFrequency: string;
  smoker: boolean;
  nutritionalStatus: string;
}

export const defaultTimersDraft: TimersDraft = {
  width: '',
  length: '',
  depth: '',
  evolutionTime: '',
  granulation: '',
  epithelialization: '',
  slough: '',
  dryNecrosis: '',
  painFactors: '',
  cultureDone: false,
  cultureResult: '',
  exudateConsistency: '',
  edgeFixation: '',
  healingSpeed: '',
  hasTunnel: false,
  tunnelLocation: '',
  periwoundMoisture: '',
  periwoundExtent: '',
  periwoundConditions: [],
  treatmentPlan: '',
  followUpDate: '',
  responsibleProfessional: '',
  registry: '',
  activityLevel: '',
  adherence: '',
  socialSupport: '',
  physicalActivity: false,
  activityDescription: '',
  alcoholUse: false,
  alcoholFrequency: '',
  smoker: false,
  nutritionalStatus: ''
};

const painLabels = ['Sem dor', 'Mínima', 'Leve', 'Incômoda', 'Moderada', 'Desconforto', 'Intensa', 'Muito intensa', 'Forte', 'Insuportável', 'Máxima'];

interface TimersStructuredSectionProps {
  register: UseFormRegister<EvaluationFormValues>;
  watch: UseFormWatch<EvaluationFormValues>;
  setValue: UseFormSetValue<EvaluationFormValues>;
  errors: FieldErrors<EvaluationFormValues>;
  draft: TimersDraft;
  setDraft: Dispatch<SetStateAction<TimersDraft>>;
  infectionSigns: string[];
  toggleArrayField: (field: 'infectionSigns' | 'comorbidities' | 'medications', value: string) => void;
}

export function TimersStructuredSection({
  register,
  watch,
  setValue,
  errors,
  draft,
  setDraft,
  infectionSigns,
  toggleArrayField
}: TimersStructuredSectionProps) {
  const painLevel = Number(watch('painLevel') || 0);
  const tissueTotal = ['granulation', 'epithelialization', 'slough', 'dryNecrosis'].reduce(
    (sum, key) => sum + (Number(draft[key as keyof TimersDraft]) || 0),
    0
  );

  const setDraftField = <K extends keyof TimersDraft>(key: K, value: TimersDraft[K]) => {
    setDraft(current => ({ ...current, [key]: value }));
  };
  const setTissuePercent = (field: 'granulation' | 'epithelialization' | 'slough' | 'dryNecrosis', value: string) => {
    const cleaned = value.replace(/[^0-9]/g, '');
    const limited = cleaned === '' ? '' : String(Math.min(Number.parseInt(cleaned, 10), 100));

    setDraft(current => {
      const next = { ...current, [field]: limited };
      const nextTotal = ['granulation', 'epithelialization', 'slough', 'dryNecrosis'].reduce(
        (sum, key) => sum + (Number(next[key as keyof TimersDraft]) || 0),
        0
      );
      return nextTotal <= 100 ? next : current;
    });
  };
  const notesField = register('notes');

  const toggleDraftArray = (key: 'periwoundConditions', value: string) => {
    setDraft(current => {
      const selected = current[key].includes(value);
      return { ...current, [key]: selected ? current[key].filter(item => item !== value) : [...current[key], value] };
    });
  };

  return (
    <div className="grid gap-4">
      <TimerPanel
        icon={<Activity className="h-5 w-5" />}
        title="T - Tecido"
        description="Dimensões, localização, etiologia e composição visual do leito da ferida."
      >
        <div className="grid gap-4 lg:grid-cols-2">
          <Select label="Localização" options={FORM_OPTIONS.woundLocations} error={errors.woundLocation?.message} {...register('woundLocation')} />
          <Select label="Etiologia" options={FORM_OPTIONS.woundEtiologies} error={errors.woundEtiology?.message} {...register('woundEtiology')} />
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-4">
          <Input label="Largura (cm)" inputMode="decimal" value={draft.width} onChange={event => setDraftField('width', event.target.value)} />
          <Input label="Comprimento (cm)" inputMode="decimal" value={draft.length} onChange={event => setDraftField('length', event.target.value)} />
          <Input label="Profundidade (cm)" inputMode="decimal" value={draft.depth} onChange={event => setDraftField('depth', event.target.value)} />
          <Input label="Tempo de evolução" value={draft.evolutionTime} onChange={event => setDraftField('evolutionTime', event.target.value)} />
        </div>

        <div className="mt-5">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-black text-heal-ink dark:text-white">Avaliação do leito da ferida</p>
            <span className={`rounded-full px-3 py-1 text-xs font-black ${tissueTotal > 100 ? 'bg-red-50 text-red-700' : 'bg-heal-softBlue text-heal-blue'}`}>
              {tissueTotal}% preenchido - {Math.max(0, 100 - tissueTotal)}% livre
            </span>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-4">
            <PercentInput label="Granulação" color="#EF4444" value={draft.granulation} onChange={value => setTissuePercent('granulation', value)} />
            <PercentInput label="Epitelização" color="#EC4899" value={draft.epithelialization} onChange={value => setTissuePercent('epithelialization', value)} />
            <PercentInput label="Esfacelo" color="#F59E0B" value={draft.slough} onChange={value => setTissuePercent('slough', value)} />
            <PercentInput label="Necrose seca" color="#111827" value={draft.dryNecrosis} onChange={value => setTissuePercent('dryNecrosis', value)} />
          </div>
          <TissueBar draft={draft} />
          <div className="mt-3 grid gap-2 text-xs font-bold text-heal-muted dark:text-zinc-400 sm:grid-cols-5">
            <LegendDot label="Granulação" color="#EF4444" value={draft.granulation} />
            <LegendDot label="Epitelização" color="#EC4899" value={draft.epithelialization} />
            <LegendDot label="Esfacelo" color="#F59E0B" value={draft.slough} />
            <LegendDot label="Necrose seca" color="#111827" value={draft.dryNecrosis} />
            <LegendDot label="Não classificado" color="#E5E7EB" value={String(Math.max(0, 100 - tissueTotal))} />
          </div>
        </div>
      </TimerPanel>

      <TimerPanel
        icon={<Flame className="h-5 w-5" />}
        title="I - Infecção e Inflamação"
        description="Escala visual de dor, fatores associados e sinais inflamatórios/infecciosos."
      >
        <div>
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-black text-heal-ink dark:text-white">Intensidade da dor</p>
            <span className="text-sm font-black text-heal-blue">
              {painLevel} - {painLabels[painLevel]}
            </span>
          </div>
          <div className="mt-3 grid grid-cols-11 overflow-hidden rounded-2xl border border-heal-line dark:border-zinc-800">
            {Array.from({ length: 11 }, (_, index) => (
              <button
                key={index}
                type="button"
                className={`min-h-11 text-sm font-black transition ${
                  painLevel === index ? 'bg-heal-blue text-white' : 'bg-white text-heal-muted hover:bg-heal-softBlue dark:bg-zinc-950 dark:hover:bg-blue-950/30'
                }`}
                onClick={() => setValue('painLevel', index, { shouldValidate: true })}
              >
                {index}
              </button>
            ))}
          </div>
        </div>
        <Textarea className="mt-4" label="Fatores que aliviam ou pioram a dor" value={draft.painFactors} onChange={event => setDraftField('painFactors', event.target.value)} />
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <CheckGroup title="Sinais de inflamação" options={FORM_OPTIONS.inflammationSigns} selected={infectionSigns} onToggle={value => toggleArrayField('infectionSigns', value)} />
          <CheckGroup title="Sinais de infecção local" options={FORM_OPTIONS.localInfectionSigns} selected={infectionSigns} onToggle={value => toggleArrayField('infectionSigns', value)} />
        </div>
        <div className="mt-4 rounded-2xl border border-heal-line bg-heal-canvas p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <ToggleChip selected={draft.cultureDone} label="Cultura da ferida realizada" onClick={() => setDraftField('cultureDone', !draft.cultureDone)} />
          {draft.cultureDone ? (
            <Input className="mt-3" label="Resultado da cultura" value={draft.cultureResult} onChange={event => setDraftField('cultureResult', event.target.value)} />
          ) : null}
        </div>
      </TimerPanel>

      <TimerPanel icon={<Droplets className="h-5 w-5" />} title="M - Umidade (Exsudato)" description="Quantidade, tipo e consistência do exsudato, como no fluxo mobile.">
        <div className="grid gap-4 md:grid-cols-3">
          <Select label="Quantidade" options={FORM_OPTIONS.exudateAmounts} error={errors.exudateAmount?.message} {...register('exudateAmount')} />
          <Select label="Tipo" options={FORM_OPTIONS.exudateTypes} error={errors.exudateType?.message} {...register('exudateType')} />
          <Select label="Consistência" options={FORM_OPTIONS.exudateConsistency} value={draft.exudateConsistency} onChange={event => setDraftField('exudateConsistency', event.target.value)} />
        </div>
      </TimerPanel>

      <TimerPanel icon={<ShieldCheck className="h-5 w-5" />} title="E - Bordas (Edge)" description="Bordas, túnel/cavidade e pele perilesional em seletores estruturados.">
        <input type="hidden" {...register('periwoundSkin')} />
        <div className="grid gap-4 md:grid-cols-3">
          <Select label="Características das bordas" options={FORM_OPTIONS.borderCharacteristics} error={errors.borderCharacteristics?.message} {...register('borderCharacteristics')} />
          <Select label="Fixação das bordas" options={FORM_OPTIONS.edgeFixations} value={draft.edgeFixation} onChange={event => setDraftField('edgeFixation', event.target.value)} />
          <Select label="Velocidade de cicatrização" options={FORM_OPTIONS.healingSpeeds} value={draft.healingSpeed} onChange={event => setDraftField('healingSpeed', event.target.value)} />
        </div>
        <div className="mt-4 rounded-2xl border border-heal-line bg-heal-canvas p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <ToggleChip selected={draft.hasTunnel} label="Presença de túneis ou cavidade" onClick={() => setDraftField('hasTunnel', !draft.hasTunnel)} />
          {draft.hasTunnel ? (
            <Input className="mt-3" label="Localização do túnel/cavidade" value={draft.tunnelLocation} onChange={event => setDraftField('tunnelLocation', event.target.value)} />
          ) : null}
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <Select label="Umidade da pele perilesional" options={FORM_OPTIONS.periwoundMoisture} value={draft.periwoundMoisture} onChange={event => setDraftField('periwoundMoisture', event.target.value)} />
          <Input label="Extensão da alteração perilesional" value={draft.periwoundExtent} onChange={event => setDraftField('periwoundExtent', event.target.value)} />
        </div>
        <CheckGroup className="mt-4" title="Condição da pele perilesional" options={FORM_OPTIONS.periwoundConditions} selected={draft.periwoundConditions} onToggle={value => toggleDraftArray('periwoundConditions', value)} />
        {errors.periwoundSkin?.message ? <p className="mt-2 text-xs font-bold text-heal-danger">{errors.periwoundSkin.message}</p> : null}
      </TimerPanel>

      <TimerPanel icon={<RefreshCw className="h-5 w-5" />} title="R - Reparo e Recomendações" description="Plano, retorno e assinatura profissional que aparecem no relatório.">
        <Textarea
          label="Observações e plano de tratamento"
          error={errors.notes?.message}
          name={notesField.name}
          ref={notesField.ref}
          onBlur={notesField.onBlur}
          onChange={event => {
            void notesField.onChange(event);
            setDraftField('treatmentPlan', event.target.value);
          }}
        />
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <Input label="Data de retorno" type="date" value={draft.followUpDate} onChange={event => setDraftField('followUpDate', event.target.value)} />
          <Input label="Profissional responsável" value={draft.responsibleProfessional} onChange={event => setDraftField('responsibleProfessional', event.target.value)} />
          <Input label="COREN/CRM" value={draft.registry} onChange={event => setDraftField('registry', event.target.value)} />
        </div>
      </TimerPanel>

      <TimerPanel icon={<UsersRound className="h-5 w-5" />} title="S - Fatores Sociais e Histórico" description="Atividade, adesão, suporte social e hábitos que influenciam cicatrização.">
        <div className="grid gap-4 md:grid-cols-2">
          <Select label="Nível de atividade" options={FORM_OPTIONS.activityLevels} value={draft.activityLevel} onChange={event => setDraftField('activityLevel', event.target.value)} />
          <Select label="Compreensão e adesão" options={FORM_OPTIONS.adherenceLevels} value={draft.adherence} onChange={event => setDraftField('adherence', event.target.value)} />
        </div>
        <Textarea className="mt-4" label="Suporte social e cuidadores" value={draft.socialSupport} onChange={event => setDraftField('socialSupport', event.target.value)} />
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <SocialToggle
            label="Pratica atividade física?"
            checked={draft.physicalActivity}
            detail={draft.activityDescription}
            detailPlaceholder="Qual atividade e frequência?"
            onToggle={() => setDraftField('physicalActivity', !draft.physicalActivity)}
            onDetailChange={value => setDraftField('activityDescription', value)}
          />
          <SocialToggle
            label="Ingere álcool?"
            checked={draft.alcoholUse}
            detail={draft.alcoholFrequency}
            detailPlaceholder="Frequência"
            onToggle={() => setDraftField('alcoholUse', !draft.alcoholUse)}
            onDetailChange={value => setDraftField('alcoholFrequency', value)}
          />
          <div className="rounded-2xl border border-heal-line bg-heal-canvas p-4 dark:border-zinc-800 dark:bg-zinc-950">
            <ToggleChip selected={draft.smoker} label="É fumante?" onClick={() => setDraftField('smoker', !draft.smoker)} />
          </div>
        </div>
        <Textarea className="mt-4" label="Avaliação nutricional" value={draft.nutritionalStatus} onChange={event => setDraftField('nutritionalStatus', event.target.value)} />
      </TimerPanel>
    </div>
  );
}

function TimerPanel({ icon, title, description, children }: { icon: ReactNode; title: string; description: string; children: ReactNode }) {
  return (
    <Card>
      <div className="mb-5 flex items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue">{icon}</div>
        <div>
          <h3 className="text-lg font-black text-heal-ink dark:text-white">{title}</h3>
          <p className="mt-1 text-sm leading-6 text-heal-muted dark:text-zinc-400">{description}</p>
        </div>
      </div>
      {children}
    </Card>
  );
}

function PercentInput({ label, color, value, onChange }: { label: string; color: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-center gap-2 text-sm font-bold text-heal-ink dark:text-white">
        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
        {label}
      </span>
      <input
        type="number"
        min={0}
        max={100}
        value={value}
        onChange={event => onChange(event.target.value)}
        className="h-11 w-full rounded-xl border border-heal-line bg-white px-3.5 text-sm font-bold text-heal-ink outline-none transition focus:border-heal-blue focus:ring-2 focus:ring-heal-blue/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
        placeholder="%"
      />
    </label>
  );
}

function TissueBar({ draft }: { draft: TimersDraft }) {
  const segments = [
    { value: Number(draft.granulation) || 0, color: '#EF4444' },
    { value: Number(draft.epithelialization) || 0, color: '#EC4899' },
    { value: Number(draft.slough) || 0, color: '#F59E0B' },
    { value: Number(draft.dryNecrosis) || 0, color: '#111827' }
  ];
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);
  const remaining = Math.max(0, 100 - total);

  return (
    <div className="mt-4 overflow-hidden rounded-full border border-heal-line bg-slate-100 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex h-4">
        {segments.map((segment, index) =>
          segment.value > 0 ? <div key={index} style={{ flex: segment.value, backgroundColor: segment.color }} /> : null
        )}
        {remaining > 0 ? <div style={{ flex: remaining }} className="bg-slate-200 dark:bg-zinc-800" /> : null}
      </div>
    </div>
  );
}

function LegendDot({ label, color, value }: { label: string; color: string; value: string }) {
  return (
    <div className="inline-flex min-w-0 items-center gap-2 rounded-full bg-heal-canvas px-3 py-2 dark:bg-zinc-950">
      <span className="h-2.5 w-2.5 shrink-0 rounded-full ring-1 ring-black/5" style={{ backgroundColor: color }} />
      <span className="truncate">{label}</span>
      <span className="ml-auto text-heal-ink dark:text-white">{Number(value) || 0}%</span>
    </div>
  );
}

function CheckGroup({
  title,
  options,
  selected,
  onToggle,
  className = ''
}: {
  title: string;
  options: readonly string[];
  selected: string[];
  onToggle: (value: string) => void;
  className?: string;
}) {
  return (
    <div className={className}>
      <p className="mb-3 text-sm font-black text-heal-ink dark:text-white">{title}</p>
      <div className="flex flex-wrap gap-2">
        {options.map(option => (
          <ToggleChip key={option} selected={selected.includes(option)} label={option} onClick={() => onToggle(option)} />
        ))}
      </div>
    </div>
  );
}

function ToggleChip({ selected, label, onClick }: { selected: boolean; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      className={`rounded-full px-3 py-1.5 text-xs font-black ring-1 transition ${
        selected
          ? 'bg-heal-blue text-white ring-heal-blue'
          : 'bg-white text-heal-muted ring-heal-line hover:bg-heal-softBlue hover:text-heal-blue dark:bg-zinc-900 dark:ring-zinc-800'
      }`}
      onClick={onClick}
    >
      {label}
    </button>
  );
}

function SocialToggle({
  label,
  checked,
  detail,
  detailPlaceholder,
  onToggle,
  onDetailChange
}: {
  label: string;
  checked: boolean;
  detail: string;
  detailPlaceholder: string;
  onToggle: () => void;
  onDetailChange: (value: string) => void;
}) {
  return (
    <div className="rounded-2xl border border-heal-line bg-heal-canvas p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <ToggleChip selected={checked} label={label} onClick={onToggle} />
      {checked ? (
        <input
          className="mt-3 h-10 w-full rounded-xl border border-heal-line bg-white px-3 text-sm text-heal-ink outline-none focus:border-heal-blue focus:ring-2 focus:ring-heal-blue/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
          value={detail}
          onChange={event => onDetailChange(event.target.value)}
          placeholder={detailPlaceholder}
        />
      ) : null}
    </div>
  );
}
