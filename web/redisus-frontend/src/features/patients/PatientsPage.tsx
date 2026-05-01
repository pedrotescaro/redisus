import { Plus, Search, Users } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../../app/providers/AuthProvider';
import { PatientCard } from '../../components/patients/PatientCard';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { Input } from '../../components/ui/Input';
import { LoadingState } from '../../components/ui/LoadingState';
import { Modal } from '../../components/ui/Modal';
import { PageHeader } from '../../components/ui/PageHeader';
import type { Patient } from '../../lib/types';
import { PatientForm } from './PatientForm';
import { createPatient, setPatientArchived, subscribePatients, updatePatient } from './patientService';
import type { PatientFormValues } from './patientSchema';

type StatusFilter = 'active' | 'archived' | 'all';

export function PatientsPage() {
  const { user } = useAuth();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<StatusFilter>('active');
  const [editing, setEditing] = useState<Patient | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    if (!user) return undefined;
    return subscribePatients(
      user.uid,
      next => {
        setPatients(next);
        setLoading(false);
      },
      () => setLoading(false)
    );
  }, [user]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return patients.filter(patient => {
      const matchesStatus =
        status === 'all' || (status === 'active' && !patient.archived) || (status === 'archived' && patient.archived);
      const matchesQuery = !normalized || patient.name.toLowerCase().includes(normalized);
      return matchesStatus && matchesQuery;
    });
  }, [patients, query, status]);

  const handleSubmit = async (values: PatientFormValues) => {
    if (!user) return;
    if (editing) await updatePatient(user.uid, editing.id, values);
    else await createPatient(user.uid, values);
    setModalOpen(false);
    setEditing(null);
  };

  const openCreate = () => {
    setEditing(null);
    setModalOpen(true);
  };

  if (loading) return <LoadingState label="Carregando pacientes do Firestore..." />;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Pacientes"
        title="Central de pacientes"
        description="Cadastre, busque, edite e arquive pacientes. Por regra de negócio, pacientes não são excluídos."
        action={
          <Button type="button" size="lg" icon={<Plus className="h-4 w-4" />} onClick={openCreate}>
            Novo paciente
          </Button>
        }
      />

      <Card className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-center">
        <Input
          aria-label="Buscar paciente"
          placeholder="Buscar por nome do paciente"
          value={query}
          onChange={event => setQuery(event.target.value)}
          icon={<Search className="h-4 w-4" />}
        />
        <div className="flex rounded-2xl border border-heal-line bg-heal-canvas p-1 dark:border-zinc-800 dark:bg-zinc-950">
          {[
            ['active', 'Ativos'],
            ['archived', 'Arquivados'],
            ['all', 'Todos']
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={`rounded-xl px-3 py-2 text-sm font-bold transition ${
                status === value ? 'bg-white text-heal-blue shadow-sm dark:bg-zinc-900' : 'text-heal-muted hover:text-heal-ink dark:hover:text-white'
              }`}
              onClick={() => setStatus(value as StatusFilter)}
            >
              {label}
            </button>
          ))}
        </div>
      </Card>

      {filtered.length ? (
        <div className="grid gap-4">
          <div className="grid gap-4 xl:grid-cols-2">
            {filtered.map(patient => (
              <PatientCard
                key={patient.id}
                patient={patient}
                onEdit={item => {
                  setEditing(item);
                  setModalOpen(true);
                }}
                onArchive={item => user && void setPatientArchived(user.uid, item.id, !item.archived)}
              />
            ))}
          </div>

          <Card className="overflow-hidden p-0">
            <div className="border-b border-heal-line px-5 py-4 dark:border-zinc-800">
              <h2 className="text-sm font-black uppercase tracking-[0.16em] text-heal-muted">Tabela rápida</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-heal-canvas text-xs uppercase tracking-wide text-heal-muted dark:bg-zinc-950">
                  <tr>
                    <th className="px-5 py-3">Nome</th>
                    <th className="px-5 py-3">Telefone</th>
                    <th className="px-5 py-3">E-mail</th>
                    <th className="px-5 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-heal-line dark:divide-zinc-800">
                  {filtered.map(patient => (
                    <tr key={patient.id} className="hover:bg-heal-canvas/70 dark:hover:bg-zinc-950">
                      <td className="px-5 py-3 font-bold text-heal-ink dark:text-white">{patient.name}</td>
                      <td className="px-5 py-3 text-heal-muted">{patient.phone}</td>
                      <td className="px-5 py-3 text-heal-muted">{patient.email || 'Não informado'}</td>
                      <td className="px-5 py-3 text-heal-muted">{patient.archived ? 'Arquivado' : 'Ativo'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      ) : (
        <EmptyState
          icon={<Users className="h-7 w-7 text-heal-blue" />}
          title="Nenhum paciente encontrado"
          description="Cadastre seu primeiro paciente para testar leitura, edição, arquivamento e regras do Firestore."
          action={<Button type="button" onClick={openCreate}>Cadastrar paciente</Button>}
        />
      )}

      <Modal open={modalOpen} title={editing ? 'Editar paciente' : 'Novo paciente'} onClose={() => setModalOpen(false)}>
        <PatientForm patient={editing} onSubmit={handleSubmit} onCancel={() => setModalOpen(false)} />
      </Modal>
    </div>
  );
}
