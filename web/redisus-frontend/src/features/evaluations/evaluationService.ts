import { supabase } from '../../lib/supabase';
import { generateUUID } from '../../lib/uuid';
import type { Evaluation, ImageDraft, WoundImage } from '../../lib/types';
import { validateImageFile } from '../../lib/validators';
import type { EvaluationFormValues } from './evaluationSchema';

export interface EvaluationWriteResult {
  id: string;
  uploadedImageCount: number;
  requestedImageCount: number;
  imageUploadError?: string;
}

interface EvaluationAuditOptions {
  previousData?: Record<string, unknown>;
  updatedBy?: string;
}

function validateEvaluationImages(images: ImageDraft[]) {
  for (const image of images) {
    if (!image.file) continue;
    const error = validateImageFile(image.file);
    if (error) throw new Error(error);
  }
}

function friendlyImageUploadError(error: unknown) {
  return typeof error === 'object' && error && 'message' in error ? String((error as any).message) : String(error);
}

function existingImageFromDraft(image: ImageDraft): WoundImage | null {
  if (!image.existingDownloadURL || !image.existingStoragePath) return null;

  return {
    id: image.id,
    storagePath: image.existingStoragePath,
    downloadURL: image.existingDownloadURL,
    fileName: image.fileName,
    contentType: image.contentType,
    size: image.size,
    rois: image.existingRois || image.rois,
    uploadedAt: new Date().toISOString()
  };
}

export function subscribeEvaluations(
  uid: string,
  patientId: string,
  onData: (evaluations: Evaluation[]) => void,
  onError?: (error: Error) => void
) {
  const fetchEvaluations = async () => {
    const { data, error } = await supabase
      .from('evaluations')
      .select('*')
      .eq('user_id', uid)
      .eq('patient_id', patientId)
      .order('date', { ascending: false });

    if (error) {
      if (onError) onError(new Error(error.message));
      return;
    }

    const mapped: Evaluation[] = (data || []).map(row => ({
      id: row.id,
      patientId: row.patient_id,
      patientName: row.patient_name || '',
      date: row.date,
      woundLocation: row.wound_location || '',
      woundEtiology: row.wound_etiology || '',
      painLevel: Number(row.pain_level || 0),
      exudateAmount: row.exudate_amount || '',
      exudateType: row.exudate_type || '',
      borderCharacteristics: row.border_characteristics || '',
      periwoundSkin: row.periwound_skin || '',
      infectionSigns: row.infection_signs || [],
      timers: row.timers || {},
      comorbidities: row.comorbidities || [],
      medications: row.medications || [],
      notes: row.notes || '',
      images: row.images || [],
      signature: row.signature || ''
    }));

    onData(mapped);
  };

  fetchEvaluations();

  const channel = supabase
    .channel(`evaluations-changes-${patientId}`)
    .on(
      'postgres_changes',
      { event: '*', schema: 'public', table: 'evaluations', filter: `patient_id=eq.${patientId}` },
      () => {
        void fetchEvaluations();
      }
    )
    .subscribe();

  return () => {
    void supabase.removeChannel(channel);
  };
}

export async function listEvaluations(uid: string, patientId: string): Promise<Evaluation[]> {
  const { data, error } = await supabase
    .from('evaluations')
    .select('*')
    .eq('user_id', uid)
    .eq('patient_id', patientId)
    .order('date', { ascending: false });

  if (error) throw new Error(error.message);

  return (data || []).map(row => ({
    id: row.id,
    patientId: row.patient_id,
    patientName: row.patient_name || '',
    date: row.date,
    woundLocation: row.wound_location || '',
    woundEtiology: row.wound_etiology || '',
    painLevel: Number(row.pain_level || 0),
    exudateAmount: row.exudate_amount || '',
    exudateType: row.exudate_type || '',
    borderCharacteristics: row.border_characteristics || '',
    periwoundSkin: row.periwound_skin || '',
    infectionSigns: row.infection_signs || [],
    timers: row.timers || {},
    comorbidities: row.comorbidities || [],
    medications: row.medications || [],
    notes: row.notes || '',
    images: row.images || [],
    signature: row.signature || ''
  }));
}

async function uploadEvaluationImages(uid: string, patientId: string, evaluationId: string, images: ImageDraft[]) {
  const uploaded: WoundImage[] = [];

  for (const image of images) {
    const existingImage = existingImageFromDraft(image);
    if (!image.file && existingImage) {
      uploaded.push(existingImage);
      continue;
    }

    if (!image.file) continue;
    const error = validateImageFile(image.file);
    if (error) throw new Error(error);

    const ext = image.file.name.split('.').pop() || 'png';
    const storagePath = `${uid}/${generateUUID()}.${ext}`;

    try {
      const { error: uploadError } = await supabase.storage
        .from('wound-images')
        .upload(storagePath, image.file, {
          contentType: image.file.type,
          upsert: false
        });

      if (uploadError) throw uploadError;

      const { data: urlData } = supabase.storage
        .from('wound-images')
        .getPublicUrl(storagePath);

      uploaded.push({
        id: image.id,
        storagePath,
        downloadURL: urlData.publicUrl,
        fileName: image.file.name,
        contentType: image.file.type,
        size: image.file.size,
        rois: image.rois,
        uploadedAt: new Date().toISOString()
      });
    } catch (uploadError: any) {
      if (existingImage) uploaded.push(existingImage);
      return { uploadedImages: uploaded, imageUploadError: friendlyImageUploadError(uploadError) };
    }
  }

  return { uploadedImages: uploaded };
}

export async function createEvaluation(uid: string, values: EvaluationFormValues, images: ImageDraft[]): Promise<EvaluationWriteResult> {
  const requestedImageCount = images.filter(image => image.file || image.existingDownloadURL).length;
  const evaluationId = generateUUID();

  validateEvaluationImages(images);
  const { uploadedImages, imageUploadError } = await uploadEvaluationImages(uid, values.patientId, evaluationId, images);

  const { error } = await supabase
    .from('evaluations')
    .insert({
      id: evaluationId,
      patient_id: values.patientId,
      user_id: uid,
      patient_name: values.patientName || '',
      date: values.date,
      wound_location: values.woundLocation || '',
      wound_etiology: values.woundEtiology || '',
      pain_level: values.painLevel,
      exudate_amount: values.exudateAmount || '',
      exudate_type: values.exudateType || '',
      border_characteristics: values.borderCharacteristics || '',
      periwound_skin: values.periwoundSkin || '',
      infection_signs: values.infectionSigns || [],
      timers: values.timers || {},
      comorbidities: values.comorbidities || [],
      medications: values.medications || [],
      notes: values.notes || '',
      images: uploadedImages,
      signature: values.signature || ''
    });

  if (error) throw new Error(error.message);

  return {
    id: evaluationId,
    uploadedImageCount: uploadedImages.length,
    requestedImageCount,
    imageUploadError
  };
}

export async function updateEvaluation(
  uid: string,
  values: EvaluationFormValues,
  evaluationId: string,
  images: ImageDraft[],
  auditOptions: EvaluationAuditOptions = {}
): Promise<EvaluationWriteResult> {
  const requestedImageCount = images.filter(image => image.file || image.existingDownloadURL).length;

  validateEvaluationImages(images);
  const { uploadedImages, imageUploadError } = await uploadEvaluationImages(uid, values.patientId, evaluationId, images);

  const { error } = await supabase
    .from('evaluations')
    .update({
      patient_name: values.patientName || '',
      date: values.date,
      wound_location: values.woundLocation || '',
      wound_etiology: values.woundEtiology || '',
      pain_level: values.painLevel,
      exudate_amount: values.exudateAmount || '',
      exudate_type: values.exudateType || '',
      border_characteristics: values.borderCharacteristics || '',
      periwound_skin: values.periwoundSkin || '',
      infection_signs: values.infectionSigns || [],
      timers: values.timers || {},
      comorbidities: values.comorbidities || [],
      medications: values.medications || [],
      notes: values.notes || '',
      images: uploadedImages,
      signature: values.signature || '',
      updated_at: new Date().toISOString()
    })
    .eq('id', evaluationId)
    .eq('user_id', uid);

  if (error) throw new Error(error.message);

  return {
    id: evaluationId,
    uploadedImageCount: uploadedImages.length,
    requestedImageCount,
    imageUploadError
  };
}
