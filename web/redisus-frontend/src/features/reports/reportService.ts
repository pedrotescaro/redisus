import { CLINICAL_DISCLAIMER } from '../../lib/constants';
import { formatDateLong } from '../../lib/date';
import { estimateRoisAreaPercent } from '../../lib/roi';
import type { Evaluation, Patient, UserProfile } from '../../lib/types';

export function buildReportTitle(patient: Patient, evaluation: Evaluation) {
  return `Relatorio Heal+ - ${patient.name} - ${formatDateLong(evaluation.date)}`;
}

export function buildEvolutionText(a: Evaluation, b: Evaluation) {
  const painDelta = b.painLevel - a.painLevel;
  const painText = painDelta === 0 ? 'dor estavel' : painDelta > 0 ? `dor aumentou ${painDelta} ponto(s)` : `dor reduziu ${Math.abs(painDelta)} ponto(s)`;
  const areaA = estimateRoisAreaPercent(a.images[0]?.rois || []);
  const areaB = estimateRoisAreaPercent(b.images[0]?.rois || []);
  const areaText = areaA && areaB ? `area visual estimada foi de ${areaA.toFixed(1)}% para ${areaB.toFixed(1)}% da imagem` : 'area visual estimada indisponivel';
  return `Entre ${formatDateLong(a.date)} e ${formatDateLong(b.date)}, ${painText}; ${areaText}. Esta comparacao e apenas estimativa visual.`;
}

export const reportDisclaimer = CLINICAL_DISCLAIMER;

export function reportSignature(profile: UserProfile | null) {
  return profile?.displayName ? `Profissional: ${profile.displayName}` : 'Profissional: nao informado';
}
