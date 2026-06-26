import { Search, SplitSquareHorizontal } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../../app/providers/AuthProvider';
import { ComparisonView } from '../../components/reports/ComparisonView';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { Input } from '../../components/ui/input';
import { LoadingState } from '../../components/ui/LoadingState';
import { PageHeader } from '../../components/ui/PageHeader';
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
    <div className="flex flex-col xl:flex-row min-h-screen min-w-0 bg-white dark:bg-[#0c0c0e]">
      {/* Coluna Central */}
      <div className="flex-grow max-w-5xl w-full border-r border-heal-line dark:border-zinc-800/60 min-h-screen flex flex-col min-w-0">
        <PageHeader
          showBack
          title="Comparar Relatórios"
          description="Evolução antes e agora de feridas"
        />

        {/* Flat selectors */}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 p-4 border-b border-heal-line/60 dark:border-zinc-800/60">
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
        </div>

        {/* Comparison view */}
        <div className="p-4 sm:p-6 flex-grow space-y-4">
          {selectedPatient && evalA && evalB && evalA.id !== evalB.id ? (
            <ComparisonView patient={selectedPatient} evaluationA={evalA} evaluationB={evalB} allEvaluations={evaluations} />
          ) : (
            <EmptyState title="Escolha duas avaliações diferentes" description="O comparativo aparece quando o paciente possui pelo menos duas avaliações salvas." />
          )}
        </div>
      </div>
    </div>
  );
}
