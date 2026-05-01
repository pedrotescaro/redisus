import { zodResolver } from '@hookform/resolvers/zod';
import { Camera, PenLine, ScanLine, Trash2, Upload } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';

import { EvaluationStepper } from '../../components/evaluations/EvaluationStepper';
import { TimersStructuredSection, defaultTimersDraft, type TimersDraft } from '../../components/evaluations/TimersStructuredSection';
import { RoiEditor } from '../../components/roi/RoiEditor';
import { RoiImageOverlay } from '../../components/roi/RoiImageOverlay';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { FORM_OPTIONS } from '../../lib/constants';
import { todayISO } from '../../lib/date';
import { formatBytes } from '../../lib/format';
import type { ImageDraft, Patient, Roi } from '../../lib/types';
import { validateImageFile } from '../../lib/validators';
import { evaluationSchema, type EvaluationFormValues } from './evaluationSchema';

interface EvaluationFormProps {
  patients: Patient[];
  defaultPatientId?: string;
  onSubmit: (values: EvaluationFormValues, images: ImageDraft[]) => Promise<void>;
}

const steps = ['Paciente', 'Clínica', 'Imagem e ROI', 'Revisão'];

const defaultValues: EvaluationFormValues = {
  patientId: '',
  patientName: '',
  date: todayISO(),
  woundLocation: '',
  woundEtiology: '',
  painLevel: 0,
  exudateAmount: '',
  exudateType: '',
  borderCharacteristics: '',
  periwoundSkin: '',
  infectionSigns: [],
  timers: {
    tissue: '',
    infection: '',
    moisture: '',
    edge: '',
    repair: '',
    social: ''
  },
  comorbidities: [],
  medications: [],
  notes: ''
};

export function EvaluationForm({ patients, defaultPatientId, onSubmit }: EvaluationFormProps) {
  const [step, setStep] = useState(0);
  const [images, setImages] = useState<ImageDraft[]>([]);
  const [imageError, setImageError] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [editingImageId, setEditingImageId] = useState<string | null>(null);
  const [timersDraft, setTimersDraft] = useState<TimersDraft>(defaultTimersDraft);
  const {
    register,
    handleSubmit,
    watch,
    trigger,
    setValue,
    formState: { errors, isSubmitting }
  } = useForm<EvaluationFormValues>({ resolver: zodResolver(evaluationSchema), defaultValues });

  const selectedPatientId = watch('patientId');
  const woundLocation = watch('woundLocation');
  const woundEtiology = watch('woundEtiology');
  const painLevel = watch('painLevel');
  const exudateAmount = watch('exudateAmount');
  const exudateType = watch('exudateType');
  const borderCharacteristics = watch('borderCharacteristics');
  const periwoundSkin = watch('periwoundSkin');
  const infectionSigns = watch('infectionSigns');
  const editingImage = useMemo(() => images.find(image => image.id === editingImageId) || null, [editingImageId, images]);

  useEffect(() => {
    if (defaultPatientId) setValue('patientId', defaultPatientId);
  }, [defaultPatientId, setValue]);

  useEffect(() => {
    const patient = patients.find(item => item.id === selectedPatientId);
    setValue('patientName', patient?.name || '');
  }, [patients, selectedPatientId, setValue]);

  useEffect(() => {
    const nextPeriwound = timersDraft.periwoundConditions.join(', ') || timersDraft.periwoundMoisture || periwoundSkin;
    if (nextPeriwound && nextPeriwound !== periwoundSkin) {
      setValue('periwoundSkin', nextPeriwound, { shouldValidate: true });
    }
  }, [periwoundSkin, setValue, timersDraft.periwoundConditions, timersDraft.periwoundMoisture]);

  useEffect(() => {
    setValue(
      'timers.tissue',
      [
        woundLocation && `Localização: ${woundLocation}`,
        woundEtiology && `Etiologia: ${woundEtiology}`,
        timersDraft.width && `Largura: ${timersDraft.width} cm`,
        timersDraft.length && `Comprimento: ${timersDraft.length} cm`,
        timersDraft.depth && `Profundidade: ${timersDraft.depth} cm`,
        timersDraft.evolutionTime && `Tempo de evolução: ${timersDraft.evolutionTime}`,
        `Leito: Granulação ${timersDraft.granulation || 0}%, Epitelização ${timersDraft.epithelialization || 0}%, Esfacelo ${timersDraft.slough || 0}%, Necrose seca ${timersDraft.dryNecrosis || 0}%`
      ]
        .filter(Boolean)
        .join(' | ')
    );
    setValue(
      'timers.infection',
      [
        `Dor: ${painLevel}/10`,
        infectionSigns.length ? `Sinais marcados: ${infectionSigns.join(', ')}` : 'Sem sinais marcados',
        timersDraft.painFactors && `Fatores da dor: ${timersDraft.painFactors}`,
        timersDraft.cultureDone && `Cultura: ${timersDraft.cultureResult || 'realizada'}`
      ]
        .filter(Boolean)
        .join(' | ')
    );
    setValue(
      'timers.moisture',
      [
        exudateAmount && `Quantidade: ${exudateAmount}`,
        exudateType && `Tipo: ${exudateType}`,
        timersDraft.exudateConsistency && `Consistência: ${timersDraft.exudateConsistency}`
      ]
        .filter(Boolean)
        .join(' | ')
    );
    setValue(
      'timers.edge',
      [
        borderCharacteristics && `Características: ${borderCharacteristics}`,
        timersDraft.edgeFixation && `Fixação: ${timersDraft.edgeFixation}`,
        timersDraft.healingSpeed && `Velocidade: ${timersDraft.healingSpeed}`,
        timersDraft.hasTunnel && `Túnel/cavidade: ${timersDraft.tunnelLocation || 'presente'}`,
        timersDraft.periwoundMoisture && `Umidade perilesional: ${timersDraft.periwoundMoisture}`,
        timersDraft.periwoundExtent && `Extensão perilesional: ${timersDraft.periwoundExtent}`,
        periwoundSkin && `Pele: ${periwoundSkin}`
      ]
        .filter(Boolean)
        .join(' | ')
    );
    setValue(
      'timers.repair',
      [
        timersDraft.treatmentPlan && `Plano: ${timersDraft.treatmentPlan}`,
        timersDraft.followUpDate && `Retorno: ${timersDraft.followUpDate}`,
        timersDraft.responsibleProfessional && `Profissional: ${timersDraft.responsibleProfessional}`,
        timersDraft.registry && `Registro: ${timersDraft.registry}`
      ]
        .filter(Boolean)
        .join(' | ')
    );
    setValue(
      'timers.social',
      [
        timersDraft.activityLevel && `Nível de atividade: ${timersDraft.activityLevel}`,
        timersDraft.adherence && `Compreensão/adesão: ${timersDraft.adherence}`,
        timersDraft.socialSupport && `Suporte social: ${timersDraft.socialSupport}`,
        timersDraft.physicalActivity && `Atividade física: ${timersDraft.activityDescription || 'sim'}`,
        timersDraft.alcoholUse && `Álcool: ${timersDraft.alcoholFrequency || 'sim'}`,
        timersDraft.smoker && 'Fumante',
        timersDraft.nutritionalStatus && `Nutrição: ${timersDraft.nutritionalStatus}`
      ]
        .filter(Boolean)
        .join(' | ')
    );
  }, [
    borderCharacteristics,
    exudateAmount,
    exudateType,
    infectionSigns,
    painLevel,
    periwoundSkin,
    setValue,
    timersDraft,
    woundEtiology,
    woundLocation
  ]);

  const addFiles = (fileList: FileList | null) => {
    setImageError('');
    if (!fileList) return;

    const drafts: ImageDraft[] = [];
    for (const file of Array.from(fileList)) {
      const error = validateImageFile(file);
      if (error) {
        setImageError(error);
        continue;
      }
      drafts.push({
        id: crypto.randomUUID(),
        file,
        previewURL: URL.createObjectURL(file),
        fileName: file.name,
        contentType: file.type,
        size: file.size,
        rois: []
      });
    }
    setImages(current => [...current, ...drafts]);
  };

  const nextStep = async () => {
    const fieldsByStep: Array<Array<keyof EvaluationFormValues>> = [
      ['patientId', 'date', 'painLevel'],
      ['woundLocation', 'woundEtiology', 'exudateAmount', 'exudateType', 'borderCharacteristics', 'periwoundSkin'],
      [],
      []
    ];
    const valid = await trigger(fieldsByStep[step]);
    if (valid) setStep(current => Math.min(current + 1, steps.length - 1));
  };

  const saveRois = (rois: Roi[]) => {
    if (!editingImageId) return;
    setImages(current => current.map(image => (image.id === editingImageId ? { ...image, rois } : image)));
    setEditingImageId(null);
  };

  const toggleArrayField = (field: 'infectionSigns' | 'comorbidities' | 'medications', value: string) => {
    const current = watch(field);
    const next = current.includes(value) ? current.filter(item => item !== value) : [...current, value];
    setValue(field, next, { shouldValidate: true });
  };

  const submitEvaluation = async (values: EvaluationFormValues) => {
    setSubmitError('');
    try {
      await onSubmit(values, images);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Não foi possível salvar a avaliação.');
    }
  };

  return (
    <form className="space-y-6" onSubmit={handleSubmit(submitEvaluation)}>
      <EvaluationStepper steps={steps} currentStep={step} />

      {step === 0 ? (
        <Card className="grid gap-4 lg:grid-cols-2">
          <Select
            label="Paciente"
            options={patients.map(patient => ({ value: patient.id, label: patient.name }))}
            placeholder="Selecione um paciente"
            value={selectedPatientId}
            onChange={event => setValue('patientId', event.target.value, { shouldValidate: true })}
            error={errors.patientId?.message}
          />
          <input type="hidden" {...register('patientId')} />
          <input type="hidden" {...register('patientName')} />
          <Input label="Data da avaliação" type="date" error={errors.date?.message} {...register('date')} />
        </Card>
      ) : null}

      {step === 1 ? (
        <div className="space-y-6">
          <TimersStructuredSection
            register={register}
            watch={watch}
            setValue={setValue}
            errors={errors}
            draft={timersDraft}
            setDraft={setTimersDraft}
            infectionSigns={infectionSigns}
            toggleArrayField={toggleArrayField}
          />

          <Card className="grid gap-5 lg:grid-cols-2">
            <Checklist title="Comorbidades" options={FORM_OPTIONS.comorbidities} selected={watch('comorbidities')} onToggle={value => toggleArrayField('comorbidities', value)} />
            <Checklist title="Medicamentos" options={FORM_OPTIONS.medications} selected={watch('medications')} onToggle={value => toggleArrayField('medications', value)} />
          </Card>
        </div>
      ) : null}

      {step === 2 ? (
        <Card>
          <div
            className="rounded-card border border-dashed border-heal-line bg-heal-canvas p-6 text-center transition hover:border-heal-blue hover:bg-heal-softBlue dark:border-zinc-800 dark:bg-zinc-950 dark:hover:bg-blue-950/30"
            onDragOver={event => event.preventDefault()}
            onDrop={event => {
              event.preventDefault();
              addFiles(event.dataTransfer.files);
            }}
          >
            <Camera className="mx-auto h-9 w-9 text-heal-blue" />
            <p className="mt-3 text-sm font-black text-heal-ink dark:text-white">Arraste imagens da ferida ou envie pelo botão</p>
            <p className="mt-1 text-xs text-heal-muted dark:text-zinc-400">Somente imagens, limite configurável em VITE_MAX_IMAGE_UPLOAD_MB.</p>
            <label className="mt-5 inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl bg-heal-blue px-4 py-2 text-sm font-bold text-white hover:bg-heal-blueDark">
              <Upload className="h-4 w-4" />
              Enviar imagem
              <input type="file" accept="image/*" multiple className="hidden" onChange={event => addFiles(event.target.files)} />
            </label>
          </div>

          {imageError ? <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-bold text-red-700">{imageError}</div> : null}

          {images.length ? (
            <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {images.map(image => (
                <div key={image.id} className="rounded-2xl border border-heal-line p-3 dark:border-zinc-800">
                  <div className="relative aspect-[4/3] overflow-hidden rounded-2xl bg-slate-100 dark:bg-zinc-950">
                    <img src={image.previewURL} alt={image.fileName} className="h-full w-full object-cover" />
                    <RoiImageOverlay rois={image.rois} />
                  </div>
                  <div className="mt-3 flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-black text-heal-ink dark:text-white">{image.fileName}</p>
                      <p className="text-xs text-heal-muted dark:text-zinc-400">{formatBytes(image.size)} - {image.rois.length} ROI(s)</p>
                    </div>
                    <div className="flex gap-2">
                      <Button type="button" variant="secondary" size="sm" icon={<ScanLine className="h-4 w-4" />} onClick={() => setEditingImageId(image.id)}>
                        ROI
                      </Button>
                      <Button type="button" variant="danger" size="sm" onClick={() => setImages(current => current.filter(item => item.id !== image.id))} aria-label="Remover imagem">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </Card>
      ) : null}

      {step === 3 ? (
        <Card>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-heal-teal">Revisão</p>
          <h3 className="mt-1 text-xl font-black text-heal-ink dark:text-white">Pronto para salvar no Firebase</h3>
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            <ReviewItem label="Paciente" value={watch('patientName') || 'Não selecionado'} />
            <ReviewItem label="Data" value={watch('date')} />
            <ReviewItem label="Dor" value={`${watch('painLevel')}/10`} />
            <ReviewItem label="Localização" value={watch('woundLocation') || 'Não informado'} />
            <ReviewItem label="Etiologia" value={watch('woundEtiology') || 'Não informado'} />
            <ReviewItem label="Imagens" value={`${images.length} arquivo(s)`} />
          </div>
          <div className="mt-5 rounded-2xl bg-heal-softBlue p-4 text-sm leading-6 text-heal-muted dark:bg-blue-950/30 dark:text-zinc-400">
            <PenLine className="mr-2 inline h-4 w-4 text-heal-blue" />
            As imagens serão enviadas ao Firebase Storage e as ROIs normalizadas ficarão salvas no documento da avaliação.
          </div>
        </Card>
      ) : null}

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
        <Button type="button" variant="secondary" onClick={() => setStep(current => Math.max(current - 1, 0))} disabled={step === 0 || isSubmitting}>
          Voltar
        </Button>
        {step < steps.length - 1 ? (
          <Button type="button" onClick={() => void nextStep()}>
            Continuar
          </Button>
        ) : (
          <Button type="submit" isLoading={isSubmitting}>
            Salvar avaliação
          </Button>
        )}
      </div>

      {submitError ? (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-bold text-red-700">
          {submitError}
        </div>
      ) : null}

      {editingImage ? (
        <RoiEditor open={!!editingImage} imageUrl={editingImage.previewURL} initialRois={editingImage.rois} onClose={() => setEditingImageId(null)} onSave={saveRois} />
      ) : null}
    </form>
  );
}

function Checklist({ title, options, selected, onToggle }: { title: string; options: readonly string[]; selected: string[]; onToggle: (value: string) => void }) {
  return (
    <div>
      <p className="mb-3 text-sm font-black text-heal-ink dark:text-white">{title}</p>
      <div className="flex flex-wrap gap-2">
        {options.map(option => (
          <button
            key={option}
            type="button"
            className={`rounded-full px-3 py-1.5 text-xs font-bold ring-1 transition ${
              selected.includes(option)
                ? 'bg-heal-blue text-white ring-heal-blue'
                : 'bg-slate-50 text-slate-600 ring-heal-line hover:bg-heal-softBlue dark:bg-zinc-950 dark:text-zinc-300 dark:ring-zinc-800'
            }`}
            onClick={() => onToggle(option)}
          >
            {option}
          </button>
        ))}
      </div>
      {selected.length ? (
        <div className="mt-3 flex flex-wrap gap-1">
          {selected.map(item => <Badge key={item} tone="blue">{item}</Badge>)}
        </div>
      ) : null}
    </div>
  );
}

function ReviewItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-heal-line bg-heal-canvas p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <p className="text-xs font-bold uppercase tracking-wide text-heal-muted">{label}</p>
      <p className="mt-1 text-sm font-black text-heal-ink dark:text-white">{value}</p>
    </div>
  );
}
