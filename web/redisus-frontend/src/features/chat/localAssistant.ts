import { formatDate } from '../../lib/date';
import type { Appointment, Evaluation, Patient } from '../../lib/types';

interface AssistantContext {
  patients: Patient[];
  appointments: Appointment[];
  evaluationsByPatient: Record<string, Evaluation[]>;
}

export function answerLocalQuestion(question: string, context: AssistantContext) {
  const normalized = question.toLowerCase();
  const active = context.patients.filter(patient => !patient.archived);
  const archived = context.patients.filter(patient => patient.archived);
  const evaluationCount = Object.values(context.evaluationsByPatient).reduce((sum, evaluations) => sum + evaluations.length, 0);
  const upcoming = context.appointments.filter(item => item.date >= new Date().toISOString().slice(0, 10));

  if (normalized.includes('ativo')) return `Você tem ${active.length} paciente(s) ativo(s).`;
  if (normalized.includes('arquivado')) return `Existem ${archived.length} paciente(s) arquivado(s).`;
  if (normalized.includes('avali')) return `Há ${evaluationCount} avaliação(ões) salvas no Firestore.`;
  if (normalized.includes('agenda') || normalized.includes('atendimento') || normalized.includes('proximo')) {
    if (!upcoming.length) return 'Não há atendimentos futuros cadastrados.';
    return `Próximos atendimentos:\n${upcoming.slice(0, 5).map(item => `- ${formatDate(item.date)} às ${item.time}: ${item.patientName} (${item.type})`).join('\n')}`;
  }

  const patient = context.patients.find(item => normalized.includes(item.name.toLowerCase()));
  if (patient) {
    const evaluations = context.evaluationsByPatient[patient.id] || [];
    const nextAppointment = upcoming.find(item => item.patientId === patient.id);
    return `${patient.name}: ${patient.archived ? 'arquivado' : 'ativo'}, ${evaluations.length} avaliação(ões), próximo atendimento: ${
      nextAppointment ? `${formatDate(nextAppointment.date)} às ${nextAppointment.time}` : 'nenhum salvo'
    }.`;
  }

  return `Resumo: ${active.length} ativos, ${archived.length} arquivados, ${evaluationCount} avaliações e ${upcoming.length} atendimento(s) futuro(s).`;
}
