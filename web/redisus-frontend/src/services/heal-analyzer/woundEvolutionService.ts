import type { ClinicalAnalysisResult, Evaluation } from '../../lib/types';

type Evolution = ClinicalAnalysisResult['evolution'];

function normalize(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

function comparePain(current?: Evaluation | null, previous?: Evaluation | null): Evolution['painTrend'] {
  if (!current || !previous) return 'unknown';
  const delta = current.painLevel - previous.painLevel;
  if (delta >= 2) return 'increased';
  if (delta <= -2) return 'decreased';
  return 'stable';
}

function compareExudate(current?: Evaluation | null, previous?: Evaluation | null): Evolution['exudateTrend'] {
  if (!current || !previous) return 'unknown';
  const currentExudate = normalize(`${current.exudateAmount} ${current.exudateType}`);
  const previousExudate = normalize(`${previous.exudateAmount} ${previous.exudateType}`);
  if (!currentExudate || !previousExudate) return 'unknown';
  return currentExudate === previousExudate ? 'stable' : 'changed';
}

function compareRegion(current?: Evaluation | null, previous?: Evaluation | null): Evolution['regionComparison'] {
  if (!current || !previous) return 'unknown';
  const currentRegion = normalize(current.woundLocation);
  const previousRegion = normalize(previous.woundLocation);
  if (!currentRegion || !previousRegion) return 'unknown';
  return currentRegion === previousRegion ? 'same' : 'different';
}

function inferGeneralTrend(painTrend: Evolution['painTrend'], exudateTrend: Evolution['exudateTrend'], previous?: Evaluation | null): Evolution['generalTrend'] {
  if (!previous) return 'insufficient_data';
  if (painTrend === 'increased' || exudateTrend === 'changed') return 'possible_worsening';
  if (painTrend === 'decreased' && exudateTrend === 'stable') return 'possible_improvement';
  if (painTrend === 'stable' && exudateTrend === 'stable') return 'stable';
  return 'insufficient_data';
}

export function findPreviousRelatedAssessment(current: Evaluation | null, history: Evaluation[]) {
  if (!current) return null;
  const currentTime = current.date ? new Date(current.date).getTime() : Number.POSITIVE_INFINITY;
  const sameRegion = history
    .filter(item => item.id !== current.id)
    .filter(item => normalize(item.woundLocation) === normalize(current.woundLocation))
    .filter(item => !item.date || new Date(item.date).getTime() <= currentTime)
    .sort((left, right) => new Date(right.date || 0).getTime() - new Date(left.date || 0).getTime());

  return sameRegion[0] || history.filter(item => item.id !== current.id)[0] || null;
}

export function buildWoundEvolution(current: Evaluation | null, history: Evaluation[]): Evolution {
  const previous = findPreviousRelatedAssessment(current, history);
  const painTrend = comparePain(current, previous);
  const exudateTrend = compareExudate(current, previous);
  const regionComparison = compareRegion(current, previous);
  const generalTrend = inferGeneralTrend(painTrend, exudateTrend, previous);

  if (!previous) {
    return {
      hasPreviousAssessment: false,
      painTrend,
      exudateTrend,
      regionComparison,
      generalTrend,
      summary: 'Nao ha avaliacoes anteriores suficientes para comparacao evolutiva.'
    };
  }

  const painCopy =
    painTrend === 'increased'
      ? 'dor aumentou'
      : painTrend === 'decreased'
        ? 'dor diminuiu'
        : painTrend === 'stable'
          ? 'dor permaneceu estavel'
          : 'tendencia de dor indefinida';
  const exudateCopy = exudateTrend === 'changed' ? 'houve mudanca no exsudato' : exudateTrend === 'stable' ? 'exsudato permaneceu estavel' : 'exsudato sem comparacao segura';

  return {
    hasPreviousAssessment: true,
    previousAssessmentId: previous.id,
    previousAssessmentDate: previous.date,
    painTrend,
    exudateTrend,
    regionComparison,
    generalTrend,
    summary: `Comparado com ${previous.date || 'avaliacao anterior'}, ${painCopy} e ${exudateCopy}. ${
      regionComparison === 'different' ? 'A regiao registrada mudou, entao a comparacao pode nao ser equivalente.' : 'A regiao registrada permanece equivalente.'
    }`
  };
}
