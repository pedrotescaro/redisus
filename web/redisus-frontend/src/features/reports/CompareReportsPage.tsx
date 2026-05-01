import { Search, SplitSquareHorizontal } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../../app/providers/AuthProvider';
import { ComparisonView } from '../../components/reports/ComparisonView';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { Input } from '../../components/ui/Input';
import { LoadingState } from '../../components/ui/LoadingState';
import { Select } from '../../components/ui/Select';
import type { Evaluation, Patient } from '../../lib/types';
import { listEvaluations } from '../evaluations/evaluationService';
import { subscribePatients } from '../patients/patientService';

export function CompareReportsPage() {
  const { user } = useAuth();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [evaluationsByPatient, setEvaluationsByPatient] = useState<Record<string, Evaluation[]>>({});
  const [patientId, setPatientId] = useState('');
  const [evalAId, setEvalAId] = useState('');
  const [evalBId, setEvalBId] = useState('');
  const [query, setQuery] = useState('');
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

  const patientOptions = useMemo(() => patients.filter(patient => (evaluationsByPatient[patient.id] || []).length >= 2), [evaluationsByPatient, patients]);
  const filteredPatients = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return patientOptions.filter(patient => !normalized || patient.name.toLowerCase().includes(normalized));
  }, [patientOptions, query]);
  const selectedPatient = patientOptions.find(patient => patient.id === patientId) || null;
  const evaluations = useMemo(
    () => (patientId ? [...(evaluationsByPatient[patientId] || [])].sort((a, b) => a.date.localeCompare(b.date)) : []),
    [evaluationsByPatient, patientId]
  );
  const evalA = evaluations.find(evaluation => evaluation.id === evalAId) || null;
  const evalB = evaluations.find(evaluation => evaluation.id === evalBId) || null;

  const selectPatient = (nextPatientId: string) => {
    setPatientId(nextPatientId);
    const nextEvaluations = [...(evaluationsByPatient[nextPatientId] || [])].sort((a, b) => a.date.localeCompare(b.date));
    setEvalAId(nextEvaluations[0]?.id || '');
    setEvalBId(nextEvaluations[nextEvaluations.length - 1]?.id || '');
  };

  if (loading) return <LoadingState label="Carregando comparativo..." />;

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-heal-teal">Comparar relatório</p>
          <h1 className="mt-1 text-3xl font-black tracking-tight text-heal-ink dark:text-white">Evolução antes e agora</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-heal-muted dark:text-zinc-400">
            Selecione um paciente e duas avaliações salvas. A estrutura clínica continua usando o modelo atual do Heal+ Web.
          </p>
        </div>
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue dark:bg-blue-950/40">
          <SplitSquareHorizontal className="h-6 w-6" />
        </div>
      </div>

      <Card className="grid gap-4 lg:grid-cols-[1fr_220px_220px]">
        <div className="grid gap-3 sm:grid-cols-[1fr_220px] lg:grid-cols-[1fr_220px]">
          <Input
            aria-label="Buscar paciente"
            label="Buscar paciente"
            placeholder="Digite o nome"
            value={query}
            onChange={event => setQuery(event.target.value)}
            icon={<Search className="h-4 w-4" />}
          />
          <Select
            label="Paciente"
            placeholder="Selecione"
            options={filteredPatients.map(patient => ({ value: patient.id, label: patient.name }))}
            value={patientId}
            onChange={event => selectPatient(event.target.value)}
          />
        </div>
        <Select
          label="Antes"
          placeholder="Avaliação inicial"
          options={evaluations.map(evaluation => ({ value: evaluation.id, label: `${evaluation.date} - ${evaluation.woundLocation}` }))}
          value={evalAId}
          onChange={event => setEvalAId(event.target.value)}
        />
        <Select
          label="Agora"
          placeholder="Avaliação recente"
          options={evaluations.map(evaluation => ({ value: evaluation.id, label: `${evaluation.date} - ${evaluation.woundLocation}` }))}
          value={evalBId}
          onChange={event => setEvalBId(event.target.value)}
        />
      </Card>

      {selectedPatient && evalA && evalB && evalA.id !== evalB.id ? (
        <ComparisonView patient={selectedPatient} evaluationA={evalA} evaluationB={evalB} allEvaluations={evaluations} />
      ) : (
        <EmptyState title="Escolha duas avaliações diferentes" description="O comparativo aparece quando o paciente possui pelo menos duas avaliações salvas." />
      )}
    </div>
  );
}
