import { Printer } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../../app/providers/AuthProvider';
import { ReportPreview } from '../../components/reports/ReportPreview';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { LoadingState } from '../../components/ui/LoadingState';
import { PageHeader } from '../../components/ui/PageHeader';
import { Select } from '../../components/ui/Select';
import type { Evaluation, Patient } from '../../lib/types';
import { listEvaluations } from '../evaluations/evaluationService';
import { subscribePatients } from '../patients/patientService';

export function ReportsPage() {
  const { user, profile } = useAuth();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [evaluationsByPatient, setEvaluationsByPatient] = useState<Record<string, Evaluation[]>>({});
  const [patientId, setPatientId] = useState('');
  const [evaluationId, setEvaluationId] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return undefined;
    return subscribePatients(user.uid, next => {
      setPatients(next);
      setLoading(false);
      void Promise.all(next.map(patient => listEvaluations(user.uid, patient.id))).then(groups => {
        setEvaluationsByPatient(Object.fromEntries(next.map((patient, index) => [patient.id, groups[index]])));
      });
    });
  }, [user]);

  const selectedPatient = patients.find(patient => patient.id === patientId) || null;
  const evaluations = patientId ? evaluationsByPatient[patientId] || [] : [];
  const selectedEvaluation = evaluations.find(evaluation => evaluation.id === evaluationId) || evaluations[0] || null;
  const patientOptions = useMemo(() => patients.filter(patient => (evaluationsByPatient[patient.id] || []).length > 0), [evaluationsByPatient, patients]);

  useEffect(() => {
    if (!patientOptions.length) {
      if (patientId) setPatientId('');
      if (evaluationId) setEvaluationId('');
      return;
    }

    if (!patientOptions.some(patient => patient.id === patientId)) {
      setPatientId(patientOptions[0].id);
      setEvaluationId('');
    }
  }, [evaluationId, patientId, patientOptions]);

  useEffect(() => {
    if (selectedEvaluation && selectedEvaluation.id !== evaluationId) setEvaluationId(selectedEvaluation.id);
  }, [evaluationId, selectedEvaluation]);

  if (loading) return <LoadingState label="Carregando relatórios..." />;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Relatórios"
        title="Documento clínico do Heal+"
        description="Prévia limpa com logo, imagem real, ROI e campos da avaliação salva no Firestore."
        action={
          <Button className="no-print" variant="secondary" icon={<Printer className="h-4 w-4" />} onClick={() => window.print()} disabled={!selectedEvaluation}>
            Imprimir / salvar PDF
          </Button>
        }
      />

      <Card className="no-print grid gap-4 md:grid-cols-2">
        <Select
          label="Paciente"
          options={patientOptions.map(patient => ({ value: patient.id, label: patient.name }))}
          value={patientId}
          onChange={event => {
            setPatientId(event.target.value);
            setEvaluationId('');
          }}
        />
        <Select
          label="Avaliação"
          options={evaluations.map(evaluation => ({ value: evaluation.id, label: `${evaluation.date} - ${evaluation.woundLocation}` }))}
          value={selectedEvaluation?.id || ''}
          onChange={event => setEvaluationId(event.target.value)}
        />
      </Card>

      {selectedPatient && selectedEvaluation ? (
        <ReportPreview patient={selectedPatient} evaluation={selectedEvaluation} profile={profile} />
      ) : (
        <EmptyState title="Selecione uma avaliação real" description="Pacientes sem avaliação não aparecem como fonte de relatório." />
      )}
    </div>
  );
}
