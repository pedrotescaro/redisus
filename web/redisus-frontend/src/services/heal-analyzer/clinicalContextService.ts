import { supabase } from '../../lib/supabase';
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

  const [patient, history] = await Promise.all([
    getPatient(options.uid, patientId),
    listEvaluations(options.uid, patientId)
  ]);
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

  const { error } = await supabase
    .from('evaluations')
    .update({
      images,
      updated_at: new Date().toISOString()
    })
    .eq('id', options.assessment.id)
    .eq('user_id', options.uid);

  if (error) throw new Error(error.message);
}

function cleanUndefined(obj: any): any {
  if (Array.isArray(obj)) {
    return obj.map(cleanUndefined);
  }
  if (obj !== null && typeof obj === 'object') {
    const cleaned: any = {};
    for (const key of Object.keys(obj)) {
      const val = obj[key];
      if (val !== undefined) {
        cleaned[key] = cleanUndefined(val);
      }
    }
    return cleaned;
  }
  return obj;
}

export async function saveClinicalAnalysisResult(options: {
  uid: string;
  result: ClinicalAnalysisResult;
}) {
  const { maskUrl: _maskUrl, overlayUrl: _overlayUrl, ...persistableSegmentation } = options.result.segmentation;
  const persistableResult: ClinicalAnalysisResult = {
    ...options.result,
    segmentation: persistableSegmentation
  };

  const { error } = await supabase
    .from('analysis_results')
    .insert({
      id: options.result.id,
      patient_id: options.result.patientId || null,
      assessment_id: options.result.assessmentId || null,
      user_id: options.uid,
      result_data: cleanUndefined(persistableResult)
    });

  if (error) throw new Error(error.message);

  return options.result.id;
}
