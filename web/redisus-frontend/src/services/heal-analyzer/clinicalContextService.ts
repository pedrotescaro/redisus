import { arrayUnion, collection, doc, serverTimestamp, setDoc, updateDoc } from 'firebase/firestore';

import { db } from '../../lib/firebase';
import { analysisResultsPath, evaluationPath, standaloneAnalysisResultsPath } from '../../lib/firestorePaths';
import { ensureClinicalRois, ROI_VERSION } from './roiProcessingService';
import { getPatient } from '../../features/patients/patientService';
import { listEvaluations } from '../../features/evaluations/evaluationService';
import type { ClinicalAnalysisResult, Evaluation, Patient, Roi } from '../../lib/types';

export interface ClinicalAnalysisContext {
  patient: Patient | null;
  assessment: Evaluation | null;
  history: Evaluation[];
  mode: 'assessment_context' | 'standalone';
}

export async function loadClinicalAnalysisContext(options: {
  uid: string;
  patientId?: string;
  assessmentId?: string;
}): Promise<ClinicalAnalysisContext> {
  const patientId = options.patientId?.trim();
  if (!patientId) {
    return { patient: null, assessment: null, history: [], mode: 'standalone' };
  }

  const [patient, history] = await Promise.all([getPatient(options.uid, patientId), listEvaluations(options.uid, patientId)]);
  const assessment = options.assessmentId ? history.find(item => item.id === options.assessmentId) || null : null;

  return {
    patient,
    assessment,
    history,
    mode: assessment ? 'assessment_context' : 'standalone'
  };
}

export async function saveAssessmentImageRois(options: {
  uid: string;
  assessment: Evaluation;
  imageId: string;
  rois: Roi[];
  updatedBy: string;
}) {
  const normalizedRois = ensureClinicalRois(options.rois).map(roi => ({
    ...roi,
    patientId: options.assessment.patientId,
    assessmentId: options.assessment.id,
    imageId: options.imageId,
    verifiedByProfessional: Boolean(roi.verifiedByProfessional),
    consentForResearch: Boolean(roi.consentForResearch),
    anonymizedExportReady: Boolean(roi.anonymizedExportReady)
  }));
  const images = options.assessment.images.map(image =>
    image.id === options.imageId
      ? {
          ...image,
          rois: normalizedRois,
          roiVersion: ROI_VERSION,
          updatedAt: new Date().toISOString(),
          updatedBy: options.updatedBy
        }
      : image
  );

  await updateDoc(doc(db, evaluationPath(options.uid, options.assessment.patientId, options.assessment.id)), {
    images,
    updatedAt: serverTimestamp(),
    updatedBy: options.updatedBy,
    auditLog: arrayUnion({
      action: 'roi_update_from_heal_analyzer',
      updatedAt: new Date().toISOString(),
      updatedBy: options.updatedBy,
      imageId: options.imageId,
      roiCount: normalizedRois.length
    })
  });
}

export async function saveClinicalAnalysisResult(options: {
  uid: string;
  result: ClinicalAnalysisResult;
}) {
  const linked = options.result.patientId && options.result.assessmentId;
  const collectionPath = linked
    ? analysisResultsPath(options.uid, options.result.patientId as string, options.result.assessmentId as string)
    : standaloneAnalysisResultsPath(options.uid);
  const resultRef = doc(collection(db, collectionPath), options.result.id);
  const { maskUrl: _maskUrl, overlayUrl: _overlayUrl, ...persistableSegmentation } = options.result.segmentation;
  const persistableResult: ClinicalAnalysisResult = {
    ...options.result,
    segmentation: persistableSegmentation
  };

  await setDoc(resultRef, {
    ...persistableResult,
    persistedAt: serverTimestamp()
  });

  return resultRef.id;
}
