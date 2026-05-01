import {
  collection,
  doc,
  getDocs,
  onSnapshot,
  orderBy,
  query,
  serverTimestamp,
  setDoc,
  updateDoc
} from 'firebase/firestore';
import { getDownloadURL, ref, uploadBytes } from 'firebase/storage';

import { db, storage, storageBucketName } from '../../lib/firebase';
import { evaluationPath, evaluationsPath } from '../../lib/firestorePaths';
import { getFileExtension, woundImagePath } from '../../lib/storagePaths';
import type { Evaluation, ImageDraft, WoundImage } from '../../lib/types';
import { validateImageFile } from '../../lib/validators';
import type { EvaluationFormValues } from './evaluationSchema';

export interface EvaluationWriteResult {
  id: string;
  uploadedImageCount: number;
  requestedImageCount: number;
  imageUploadError?: string;
}

const mapEvaluation = (id: string, data: Record<string, unknown>): Evaluation => ({
  id,
  patientId: String(data.patientId || ''),
  patientName: String(data.patientName || ''),
  date: String(data.date || ''),
  woundLocation: String(data.woundLocation || ''),
  woundEtiology: String(data.woundEtiology || ''),
  painLevel: Number(data.painLevel || 0),
  exudateAmount: String(data.exudateAmount || ''),
  exudateType: String(data.exudateType || ''),
  borderCharacteristics: String(data.borderCharacteristics || ''),
  periwoundSkin: String(data.periwoundSkin || ''),
  infectionSigns: Array.isArray(data.infectionSigns) ? data.infectionSigns.map(String) : [],
  timers: {
    tissue: String((data.timers as Record<string, unknown>)?.tissue || ''),
    infection: String((data.timers as Record<string, unknown>)?.infection || ''),
    moisture: String((data.timers as Record<string, unknown>)?.moisture || ''),
    edge: String((data.timers as Record<string, unknown>)?.edge || ''),
    repair: String((data.timers as Record<string, unknown>)?.repair || ''),
    social: String((data.timers as Record<string, unknown>)?.social || '')
  },
  comorbidities: Array.isArray(data.comorbidities) ? data.comorbidities.map(String) : [],
  medications: Array.isArray(data.medications) ? data.medications.map(String) : [],
  notes: String(data.notes || ''),
  images: Array.isArray(data.images) ? (data.images as WoundImage[]) : [],
  imageUploadStatus: data.imageUploadStatus === 'failed' || data.imageUploadStatus === 'complete' ? data.imageUploadStatus : undefined,
  imageUploadError: typeof data.imageUploadError === 'string' ? data.imageUploadError : null,
  createdAt: data.createdAt as Evaluation['createdAt'],
  updatedAt: data.updatedAt as Evaluation['updatedAt']
});

function validateEvaluationImages(images: ImageDraft[]) {
  for (const image of images) {
    if (!image.file) continue;
    const error = validateImageFile(image.file);
    if (error) throw new Error(error);
  }
}

function friendlyImageUploadError(error: unknown) {
  const code = typeof error === 'object' && error && 'code' in error ? String((error as { code?: unknown }).code) : '';

  if (code === 'storage/unauthorized') {
    return 'A avaliação foi salva, mas as regras do Firebase Storage bloquearam o envio das imagens.';
  }

  if (code === 'storage/canceled') {
    return 'A avaliação foi salva, mas o envio das imagens foi cancelado.';
  }

  return 'A avaliação foi salva sem imagens porque o Firebase Storage não está disponível para este projeto. Crie/ative o bucket do Storage e tente enviar as imagens novamente.';
}

let storageBucketCheck: Promise<string | null> | null = null;

async function getStorageBucketError() {
  if (!storageBucketName || storageBucketName.startsWith('missing-')) {
    return 'A avaliação foi salva sem imagens porque o bucket do Firebase Storage não está configurado.';
  }

  if (typeof fetch === 'undefined') return null;

  storageBucketCheck ??= fetch(`https://firebasestorage.googleapis.com/v0/b/${encodeURIComponent(storageBucketName)}/o?maxResults=1`)
    .then(response => {
      if (response.status === 404) {
        return `A avaliação foi salva sem imagens porque o bucket ${storageBucketName} ainda não existe. Ative o Firebase Storage no plano Blaze e tente enviar as imagens novamente.`;
      }
      return null;
    })
    .catch(() => null);

  return storageBucketCheck;
}

export function subscribeEvaluations(
  uid: string,
  patientId: string,
  onData: (evaluations: Evaluation[]) => void,
  onError?: (error: Error) => void
) {
  return onSnapshot(
    query(collection(db, evaluationsPath(uid, patientId)), orderBy('date', 'desc')),
    snapshot => onData(snapshot.docs.map(item => mapEvaluation(item.id, item.data()))),
    onError
  );
}

export async function listEvaluations(uid: string, patientId: string) {
  const snapshot = await getDocs(query(collection(db, evaluationsPath(uid, patientId)), orderBy('date', 'desc')));
  return snapshot.docs.map(item => mapEvaluation(item.id, item.data()));
}

async function uploadEvaluationImages(uid: string, patientId: string, evaluationId: string, images: ImageDraft[]) {
  const uploaded: WoundImage[] = [];

  for (const image of images) {
    if (!image.file && image.existingDownloadURL && image.existingStoragePath) {
      uploaded.push({
        id: image.id,
        storagePath: image.existingStoragePath,
        downloadURL: image.existingDownloadURL,
        fileName: image.fileName,
        contentType: image.contentType,
        size: image.size,
        rois: image.rois,
        uploadedAt: new Date().toISOString()
      });
      continue;
    }

    if (!image.file) continue;
    const error = validateImageFile(image.file);
    if (error) throw new Error(error);

    const bucketError = await getStorageBucketError();
    if (bucketError) return { uploadedImages: uploaded, imageUploadError: bucketError };

    const path = woundImagePath(uid, patientId, evaluationId, image.id, getFileExtension(image.file));
    const fileRef = ref(storage, path);
    let downloadURL = '';

    try {
      await uploadBytes(fileRef, image.file, { contentType: image.file.type });
      downloadURL = await getDownloadURL(fileRef);
    } catch (error) {
      return { uploadedImages: uploaded, imageUploadError: friendlyImageUploadError(error) };
    }

    uploaded.push({
      id: image.id,
      storagePath: path,
      downloadURL,
      fileName: image.file.name,
      contentType: image.file.type,
      size: image.file.size,
      rois: image.rois,
      uploadedAt: new Date().toISOString()
    });
  }

  return { uploadedImages: uploaded };
}

export async function createEvaluation(uid: string, values: EvaluationFormValues, images: ImageDraft[]) {
  const evaluationRef = doc(collection(db, evaluationsPath(uid, values.patientId)));
  const requestedImageCount = images.filter(image => image.file || image.existingDownloadURL).length;

  validateEvaluationImages(images);
  const { uploadedImages, imageUploadError } = await uploadEvaluationImages(uid, values.patientId, evaluationRef.id, images);

  await setDoc(evaluationRef, {
    ...values,
    images: uploadedImages,
    imageUploadStatus: imageUploadError ? 'failed' : 'complete',
    imageUploadError: imageUploadError || null,
    createdAt: serverTimestamp(),
    updatedAt: serverTimestamp()
  });

  return {
    id: evaluationRef.id,
    uploadedImageCount: uploadedImages.length,
    requestedImageCount,
    imageUploadError
  };
}

export async function updateEvaluation(uid: string, values: EvaluationFormValues, evaluationId: string, images: ImageDraft[]) {
  const requestedImageCount = images.filter(image => image.file || image.existingDownloadURL).length;

  validateEvaluationImages(images);
  const { uploadedImages, imageUploadError } = await uploadEvaluationImages(uid, values.patientId, evaluationId, images);

  await updateDoc(doc(db, evaluationPath(uid, values.patientId, evaluationId)), {
    ...values,
    images: uploadedImages,
    imageUploadStatus: imageUploadError ? 'failed' : 'complete',
    imageUploadError: imageUploadError || null,
    updatedAt: serverTimestamp()
  });

  return {
    id: evaluationId,
    uploadedImageCount: uploadedImages.length,
    requestedImageCount,
    imageUploadError
  };
}
