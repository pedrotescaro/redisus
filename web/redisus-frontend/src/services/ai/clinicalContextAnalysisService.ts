import type { ClinicalAnalysisAlert, Evaluation, Patient } from '../../lib/types';
import type { WoundImageQualityResult } from './imageQualityService';
import type { RoiValidationResult } from './woundInputValidationService';

export interface ClinicalContextAnalysisResult {
  patientName?: string;
  patientStatus?: string;
  patientAge?: number | null;
  painLevel?: number;
  exudate?: string;
  woundRegion?: string;
  woundType?: string;
  observations?: string;
  odor?: string;
  consideredFields: string[];
  missingFields: string[];
}

function normalize(value?: string | null) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

function getAgeFromBirthDate(birthDate?: string) {
  if (!birthDate) return null;
  const birth = new Date(birthDate);
  if (Number.isNaN(birth.getTime())) return null;
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const monthDelta = today.getMonth() - birth.getMonth();
  if (monthDelta < 0 || (monthDelta === 0 && today.getDate() < birth.getDate())) age -= 1;
  return age >= 0 && age < 130 ? age : null;
}

function exudateText(assessment: Evaluation | null) {
  if (!assessment) return '';
  return [assessment.exudateAmount, assessment.exudateType].filter(Boolean).join(' / ');
}

function missingClinicalFields(assessment: Evaluation | null) {
  if (!assessment) return ['avaliacao', 'regiao', 'tipo_lesao', 'dor', 'exsudato'];
  const missing: string[] = [];
  if (!assessment.woundLocation) missing.push('regiao');
  if (!assessment.woundEtiology) missing.push('tipo_lesao');
  if (assessment.painLevel === undefined || assessment.painLevel === null) missing.push('dor');
  if (!assessment.exudateAmount) missing.push('quantidade_exsudato');
  if (!assessment.exudateType) missing.push('tipo_exsudato');
  if (!assessment.notes) missing.push('observacoes');
  return missing;
}

function getOdorHint(assessment: Evaluation | null) {
  if (!assessment) return '';
  const infectionSigns = assessment.infectionSigns.map(normalize);
  const notes = normalize(assessment.notes);
  if (infectionSigns.some(sign => sign.includes('odor')) || notes.includes('odor') || notes.includes('fetid')) {
    return 'odor relatado ou sugerido nos dados preenchidos';
  }
  return '';
}

function addAlert(alerts: ClinicalAnalysisAlert[], severity: ClinicalAnalysisAlert['severity'], title: string, message: string) {
  alerts.push({ severity, title, message });
}

export function buildClinicalContextAnalysis(patient: Patient | null, assessment: Evaluation | null): ClinicalContextAnalysisResult {
  const consideredFields: string[] = [];
  if (patient?.name) consideredFields.push('paciente');
  if (patient?.birthDate) consideredFields.push('data_nascimento');
  if (assessment?.date) consideredFields.push('data_avaliacao');
  if (assessment?.woundLocation) consideredFields.push('regiao');
  if (assessment?.woundEtiology) consideredFields.push('tipo_lesao');
  if (assessment?.painLevel !== undefined) consideredFields.push('dor');
  if (assessment?.exudateAmount || assessment?.exudateType) consideredFields.push('exsudato');
  if (assessment?.borderCharacteristics) consideredFields.push('bordas');
  if (assessment?.periwoundSkin) consideredFields.push('pele_ao_redor');
  if (assessment?.notes) consideredFields.push('observacoes');

  return {
    patientName: patient?.name,
    patientStatus: patient ? (patient.archived ? 'Arquivado' : 'Ativo') : undefined,
    patientAge: getAgeFromBirthDate(patient?.birthDate),
    painLevel: assessment?.painLevel,
    woundRegion: assessment?.woundLocation,
    woundType: assessment?.woundEtiology,
    exudate: exudateText(assessment),
    odor: getOdorHint(assessment),
    observations: assessment?.notes,
    consideredFields,
    missingFields: missingClinicalFields(assessment)
  };
}

export function buildClinicalContextAlerts(options: {
  assessment: Evaluation | null;
  clinicalContext: ClinicalContextAnalysisResult;
  imageQuality: WoundImageQualityResult;
  roiValidation?: RoiValidationResult;
}) {
  const alerts: ClinicalAnalysisAlert[] = [];
  const { assessment, clinicalContext, imageQuality, roiValidation } = options;

  if (imageQuality.status === 'poor') {
    addAlert(alerts, 'medium', 'Qualidade de imagem limitada', 'Foco, iluminação, contraste ou resolução podem comprometer a leitura assistiva.');
  }

  if (roiValidation && !roiValidation.isValid) {
    addAlert(alerts, 'high', 'Imagem não adequada para análise de ferida', roiValidation.reason);
  }

  if (assessment && assessment.painLevel >= 8) {
    addAlert(alerts, assessment.painLevel >= 9 ? 'high' : 'medium', 'Dor elevada', `A avaliação registra dor ${assessment.painLevel}/10, exigindo atenção no acompanhamento clínico.`);
  }

  const exudate = normalize(exudateText(assessment));
  if (exudate.includes('purulent') || exudate.includes('purulento') || exudate.includes('seropurulent')) {
    addAlert(alerts, 'medium', 'Padrão de exsudato merece atenção', 'O exsudato informado deve ser correlacionado com exame físico, sem caracterizar diagnóstico definitivo.');
  }

  if (clinicalContext.odor) {
    addAlert(alerts, 'medium', 'Odor relatado', 'Há registro de odor nos dados clínicos, achado que deve ser validado pelo profissional responsável.');
  }

  if (clinicalContext.missingFields.length) {
    addAlert(alerts, 'low', 'Dados clínicos incompletos', 'Campos ausentes reduzem a capacidade de análise contextual e comparação evolução.');
  }

  return alerts;
}

export function buildClinicalContextRecommendations(options: {
  canAnalyze: boolean;
  imageQuality: WoundImageQualityResult;
  hasPatient: boolean;
  hasAssessment: boolean;
}) {
  const recommendations = [
    'Validar os achados com o profissional responsável e com o exame físico.',
    'Manter fotos com mesmo padrão de distância, ângulo e iluminação.',
    'Registrar evolução com frequência e revisar dor, exsudato, bordas e pele ao redor.'
  ];

  if (!options.canAnalyze) {
    recommendations.unshift('Refazer a foto clínica ou ajustar a ROI antes de tentar nova análise visual.');
  }
  if (options.imageQuality.status !== 'good') {
    recommendations.unshift('Refazer a foto com boa iluminação, foco e enquadramento quando possível.');
  }
  if (!options.hasPatient) recommendations.push('Vincular um paciente para permitir análise contextual e histórico longitudinal.');
  if (!options.hasAssessment) recommendations.push('Vincular uma avaliação para considerar dados clínicos estruturados.');
  recommendations.push('Considerar avaliação presencial se houver sinais de agravamento, dor intensa, odor, calor local ou piora do exsudato.');
  return recommendations;
}
