import { Upload } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';

import { RoiImageOverlay } from '../../components/roi/RoiImageOverlay';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Modal } from '../../components/ui/Modal';
import { Select } from '../../components/ui/Select';
import { Textarea } from '../../components/ui/textarea';
import { FORM_OPTIONS } from '../../lib/constants';
import type { Evaluation, ImageDraft, WoundImage } from '../../lib/types';
import type { EvaluationFormValues } from '../evaluations/evaluationSchema';

interface ClinicalEvaluationEditModalProps {
  evaluation: Evaluation | null;
  open: boolean;
  error?: string;
  saving?: boolean;
  onClose: () => void;
  onSave: (values: EvaluationFormValues, images: ImageDraft[]) => Promise<void>;
}

interface EditDraft {
  date: string;
  woundLocation: string;
  woundEtiology: string;
  painLevel: string;
  exudateAmount: string;
  exudateType: string;
  borderCharacteristics: string;
  periwoundSkin: string;
  infectionSigns: string[];
  comorbidities: string[];
  medications: string[];
  notes: string;
}

const defaultTimers = {
  tissue: '',
  infection: '',
  moisture: '',
  edge: '',
  repair: '',
  social: ''
};

function draftFromEvaluation(evaluation: Evaluation): EditDraft {
  return {
    date: evaluation.date,
    woundLocation: evaluation.woundLocation,
    woundEtiology: evaluation.woundEtiology,
    painLevel: String(evaluation.painLevel),
    exudateAmount: evaluation.exudateAmount,
    exudateType: evaluation.exudateType,
    borderCharacteristics: evaluation.borderCharacteristics || '',
    periwoundSkin: evaluation.periwoundSkin || '',
    infectionSigns: evaluation.infectionSigns || [],
    comorbidities: evaluation.comorbidities || [],
    medications: evaluation.medications || [],
    notes: evaluation.notes || ''
  };
}

function optionsWithCurrent(options: readonly string[], current: string) {
  const trimmed = current.trim();
  if (!trimmed || options.includes(trimmed)) return options;
  return [trimmed, ...options];
}

function createDraftId() {
  return typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `image-${Date.now()}`;
}

function existingImageDraft(image: WoundImage): ImageDraft {
  return {
    id: image.id,
    previewURL: image.downloadURL,
    fileName: image.fileName,
    contentType: image.contentType,
    size: image.size,
    existingStoragePath: image.storagePath,
    existingDownloadURL: image.downloadURL,
    existingRois: image.rois,
    rois: image.rois
  };
}

function imageDraftsForSave(evaluation: Evaluation, replacementImage: File | null, previewURL: string) {
  const existingDrafts = evaluation.images.map(existingImageDraft);
  if (!replacementImage) return existingDrafts;

  const [firstImage, ...remainingImages] = existingDrafts;
  const replacementDraft: ImageDraft = {
    id: firstImage?.id || createDraftId(),
    file: replacementImage,
    previewURL,
    fileName: replacementImage.name,
    contentType: replacementImage.type,
    size: replacementImage.size,
    existingStoragePath: firstImage?.existingStoragePath,
    existingDownloadURL: firstImage?.existingDownloadURL,
    existingRois: firstImage?.rois,
    rois: []
  };

  return [replacementDraft, ...remainingImages];
}

function validationErrors(draft: EditDraft) {
  const errors: Partial<Record<keyof EditDraft, string>> = {};
  const painLevel = Number(draft.painLevel);

  if (!draft.date) errors.date = 'Informe a data da avaliação.';
  if (draft.woundLocation.trim().length < 2) errors.woundLocation = 'Informe a região da ferida.';
  if (draft.woundEtiology.trim().length < 2) errors.woundEtiology = 'Informe o tipo de lesão.';
  if (!Number.isFinite(painLevel) || painLevel < 0 || painLevel > 10) errors.painLevel = 'Informe um nível de dor entre 0 e 10.';
  if (!draft.exudateAmount) errors.exudateAmount = 'Informe a quantidade de exsudato.';
  if (!draft.exudateType) errors.exudateType = 'Informe o tipo de exsudato.';

  return errors;
}

export function ClinicalEvaluationEditModal({
  evaluation,
  open,
  error,
  saving = false,
  onClose,
  onSave
}: ClinicalEvaluationEditModalProps) {
  const [draft, setDraft] = useState<EditDraft | null>(evaluation ? draftFromEvaluation(evaluation) : null);
  const [errors, setErrors] = useState<Partial<Record<keyof EditDraft, string>>>({});
  const [replacementImage, setReplacementImage] = useState<File | null>(null);
  const [replacementPreviewURL, setReplacementPreviewURL] = useState('');

  useEffect(() => {
    if (!evaluation || !open) return;
    setDraft(draftFromEvaluation(evaluation));
    setErrors({});
    setReplacementImage(null);
    setReplacementPreviewURL('');
  }, [evaluation, open]);

  useEffect(() => {
    if (!replacementImage) {
      setReplacementPreviewURL('');
      return undefined;
    }

    const objectURL = URL.createObjectURL(replacementImage);
    setReplacementPreviewURL(objectURL);
    return () => URL.revokeObjectURL(objectURL);
  }, [replacementImage]);

  if (!evaluation || !draft) return null;

  const previewURL = replacementPreviewURL || evaluation.images[0]?.downloadURL || '';
  const previewRois = replacementPreviewURL ? [] : evaluation.images[0]?.rois || [];

  const updateDraft = (field: keyof EditDraft, value: any) => {
    setDraft(current => (current ? { ...current, [field]: value } : current));
    setErrors(current => ({ ...current, [field]: undefined }));
  };

  const toggleArrayItem = (field: 'infectionSigns' | 'comorbidities' | 'medications', item: string) => {
    if (!draft) return;
    const currentArray = draft[field] || [];
    const nextArray = currentArray.includes(item)
      ? currentArray.filter(i => i !== item)
      : [...currentArray, item];
    updateDraft(field, nextArray);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors = validationErrors(draft);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;

    const values: EvaluationFormValues = {
      patientId: evaluation.patientId,
      patientName: evaluation.patientName,
      date: draft.date,
      woundLocation: draft.woundLocation.trim(),
      woundEtiology: draft.woundEtiology.trim(),
      painLevel: Number(draft.painLevel),
      exudateAmount: draft.exudateAmount,
      exudateType: draft.exudateType,
      borderCharacteristics: draft.borderCharacteristics.trim(),
      periwoundSkin: draft.periwoundSkin.trim(),
      infectionSigns: draft.infectionSigns,
      timers: evaluation.timers || defaultTimers,
      comorbidities: draft.comorbidities,
      medications: draft.medications,
      notes: draft.notes.trim()
    };

    await onSave(values, imageDraftsForSave(evaluation, replacementImage, replacementPreviewURL));
  };

  return (
    <Modal open={open} title="Editar registro clínico" onClose={onClose} size="xl">
      <form className="space-y-5" onSubmit={submit}>
        <div className="grid gap-5 lg:grid-cols-[220px_1fr]">
          <div className="space-y-3">
            <div className="relative aspect-[4/3] overflow-hidden rounded-2xl bg-slate-950">
              {previewURL ? (
                <>
                  <img src={previewURL} alt="" className="h-full w-full object-contain" />
                  <RoiImageOverlay rois={previewRois} />
                </>
              ) : (
                <div className="flex h-full items-center justify-center px-4 text-center text-xs font-semibold text-slate-400">
                  Sem imagem cadastrada
                </div>
              )}
            </div>
            <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-heal-line bg-white px-3 py-2 text-sm font-bold text-heal-blue transition hover:border-heal-blue hover:bg-heal-softBlue dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-blue-950/30">
              <Upload className="h-4 w-4" />
              Substituir imagem
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={event => setReplacementImage(event.target.files?.[0] || null)}
              />
            </label>
            <p className="text-xs leading-5 text-heal-muted dark:text-zinc-400">
              Opcional. Se nenhuma imagem for selecionada, a imagem atual é mantida.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Input
              label="Data da avaliação"
              type="date"
              value={draft.date}
              onChange={event => updateDraft('date', event.target.value)}
              error={errors.date}
            />
            <Input
              label="Nível de dor"
              type="number"
              min={0}
              max={10}
              value={draft.painLevel}
              onChange={event => updateDraft('painLevel', event.target.value)}
              error={errors.painLevel}
            />
            <Select
              label="Região da ferida"
              value={draft.woundLocation}
              options={optionsWithCurrent(FORM_OPTIONS.woundLocations, draft.woundLocation)}
              onChange={event => updateDraft('woundLocation', event.target.value)}
              error={errors.woundLocation}
            />
            <Select
              label="Tipo de lesão"
              value={draft.woundEtiology}
              options={optionsWithCurrent(FORM_OPTIONS.woundEtiologies, draft.woundEtiology)}
              onChange={event => updateDraft('woundEtiology', event.target.value)}
              error={errors.woundEtiology}
            />
            <Select
              label="Quantidade de exsudato"
              value={draft.exudateAmount}
              options={optionsWithCurrent(FORM_OPTIONS.exudateAmounts, draft.exudateAmount)}
              onChange={event => updateDraft('exudateAmount', event.target.value)}
              error={errors.exudateAmount}
            />
            <Select
              label="Tipo de exsudato"
              value={draft.exudateType}
              options={optionsWithCurrent(FORM_OPTIONS.exudateTypes, draft.exudateType)}
              onChange={event => updateDraft('exudateType', event.target.value)}
              error={errors.exudateType}
            />
            <Select
              label="Características da borda"
              value={draft.borderCharacteristics}
              options={optionsWithCurrent(FORM_OPTIONS.borderCharacteristics, draft.borderCharacteristics)}
              onChange={event => updateDraft('borderCharacteristics', event.target.value)}
              error={errors.borderCharacteristics}
            />
            <Select
              label="Pele perilesional"
              value={draft.periwoundSkin}
              options={optionsWithCurrent(FORM_OPTIONS.periwoundSkin, draft.periwoundSkin)}
              onChange={event => updateDraft('periwoundSkin', event.target.value)}
              error={errors.periwoundSkin}
            />
            <div className="md:col-span-2 border-t border-heal-line/60 dark:border-zinc-800/60 pt-4">
              <p className="text-xs font-bold uppercase tracking-wider text-heal-muted mb-2">Sinais de Infecção</p>
              <div className="flex flex-wrap gap-2">
                {FORM_OPTIONS.infectionSigns.map(sign => {
                  const checked = draft.infectionSigns.includes(sign);
                  return (
                    <label key={sign} className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-bold transition cursor-pointer select-none ${
                      checked
                        ? 'border-red-500 bg-red-50/50 text-red-700 dark:bg-red-950/20 dark:text-red-300'
                        : 'border-heal-line bg-white hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800/50 text-heal-muted'
                    }`}>
                      <input
                        type="checkbox"
                        checked={checked}
                        className="sr-only"
                        onChange={() => toggleArrayItem('infectionSigns', sign)}
                      />
                      {sign}
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="md:col-span-2 border-t border-heal-line/60 dark:border-zinc-800/60 pt-4">
              <p className="text-xs font-bold uppercase tracking-wider text-heal-muted mb-2">Comorbidades</p>
              <div className="flex flex-wrap gap-2">
                {FORM_OPTIONS.comorbidities.map(c => {
                  const checked = draft.comorbidities.includes(c);
                  return (
                    <label key={c} className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-bold transition cursor-pointer select-none ${
                      checked
                        ? 'border-heal-blue bg-heal-softBlue/50 text-heal-blue dark:bg-blue-950/20 dark:text-blue-300'
                        : 'border-heal-line bg-white hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800/50 text-heal-muted'
                    }`}>
                      <input
                        type="checkbox"
                        checked={checked}
                        className="sr-only"
                        onChange={() => toggleArrayItem('comorbidities', c)}
                      />
                      {c}
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="md:col-span-2 border-t border-heal-line/60 dark:border-zinc-800/60 pt-4">
              <p className="text-xs font-bold uppercase tracking-wider text-heal-muted mb-2">Medicamentos em uso</p>
              <div className="flex flex-wrap gap-2">
                {FORM_OPTIONS.medications.map(m => {
                  const checked = draft.medications.includes(m);
                  return (
                    <label key={m} className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-bold transition cursor-pointer select-none ${
                      checked
                        ? 'border-purple-500 bg-purple-50/50 text-purple-700 dark:bg-purple-950/20 dark:text-purple-300'
                        : 'border-heal-line bg-white hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800/50 text-heal-muted'
                    }`}>
                      <input
                        type="checkbox"
                        checked={checked}
                        className="sr-only"
                        onChange={() => toggleArrayItem('medications', m)}
                      />
                      {m}
                    </label>
                  );
                })}
              </div>
            </div>
            <Textarea
              className="md:col-span-2 border-t border-heal-line/60 dark:border-zinc-800/60 pt-4"
              label="Observações clínicas"
              value={draft.notes}
              onChange={event => updateDraft('notes', event.target.value)}
              helperText="Registre apenas informações fiéis ao atendimento realizado."
            />
          </div>
        </div>

        {error ? (
          <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-bold text-red-700">
            {error}
          </div>
        ) : null}

        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
            Cancelar
          </Button>
          <Button type="submit" isLoading={saving}>
            Salvar alterações
          </Button>
        </div>
      </form>
    </Modal>
  );
}
