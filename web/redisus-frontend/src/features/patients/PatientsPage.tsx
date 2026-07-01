import { Plus, Search, Users } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../../app/providers/AuthProvider';
import { PatientCard } from '../../components/patients/PatientCard';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { Input } from '../../components/ui/input';
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

  const PATIENTS_PAGE_SIZE = 6;
  const [visibleCount, setVisibleCount] = useState(PATIENTS_PAGE_SIZE);

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

  useEffect(() => {
    setVisibleCount(PATIENTS_PAGE_SIZE);
  }, [query, status]);

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

  const quickTableCard = (
    <Card className="overflow-hidden p-0 border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e]">
      <div className="border-b border-heal-line/60 px-5 py-4 dark:border-zinc-800/80">
        <h2 className="text-xs font-black uppercase tracking-[0.16em] text-heal-muted">Tabela rápida</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-heal-canvas/40 text-xs uppercase tracking-wide text-heal-muted dark:bg-zinc-950/40">
            <tr>
              <th className="px-5 py-2.5">Nome</th>
              <th className="px-5 py-2.5">Telefone</th>
              <th className="px-5 py-2.5">E-mail</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-heal-line/60 dark:divide-zinc-800/60">
            {filtered.slice(0, visibleCount).map(patient => (
              <tr key={patient.id} className="hover:bg-heal-canvas/30 dark:hover:bg-zinc-900/30 transition-colors">
                <td className="px-5 py-3 font-bold text-heal-ink dark:text-white truncate max-w-[180px]">{patient.name}</td>
                <td className="px-5 py-3 text-xs text-heal-muted truncate">{patient.phone}</td>
                <td className="px-5 py-3 text-xs text-heal-muted truncate">{patient.email || 'Não informado'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );

  if (loading) return <LoadingState label="Carregando pacientes do Firestore..." />;

  return (
    <div className="flex flex-col xl:flex-row min-h-screen min-w-0 bg-white dark:bg-[#0c0c0e]">
      {/* Coluna Central */}
      <div className="flex-grow max-w-5xl w-full border-r border-heal-line dark:border-zinc-800/60 min-h-screen flex flex-col min-w-0">
        <PageHeader
          title="Central de pacientes"
          description={`${filtered.length} ${filtered.length === 1 ? 'paciente cadastrado' : 'pacientes cadastrados'}`}
          action={
            <Button type="button" size="lg" icon={<Plus className="h-4 w-4" />} onClick={openCreate}>
              Novo paciente
            </Button>
          }
        />

        {/* Flat search and filter container */}
        <div className="p-4 border-b border-heal-line/60 dark:border-zinc-800/60 space-y-4">
          <Input
            aria-label="Buscar paciente"
            placeholder="Buscar por nome do paciente..."
            value={query}
            onChange={event => setQuery(event.target.value)}
            icon={<Search className="h-4 w-4" />}
          />
          <div className="flex w-full select-none">
            {[
              ['active', 'Ativos'],
              ['archived', 'Arquivados'],
              ['all', 'Todos']
            ].map(([value, label]) => {
              const active = status === value;
              return (
                <button
                  key={value}
                  type="button"
                  className={`relative flex-1 py-3 text-xs font-bold transition-colors text-center cursor-pointer ${
                    active ? 'text-heal-ink dark:text-white' : 'text-heal-muted hover:text-heal-ink dark:hover:text-white'
                  }`}
                  onClick={() => setStatus(value as StatusFilter)}
                >
                  {label}
                  {active && <div className="absolute bottom-0 left-1/4 right-1/4 h-0.5 rounded-full bg-heal-blue" />}
                </button>
              );
            })}
          </div>
        </div>

        {/* Content list */}
        <div className="p-4 sm:p-6 flex-grow space-y-4">
          {filtered.length ? (
            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                {filtered.slice(0, visibleCount).map(patient => (
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

              {visibleCount < filtered.length && (
                <div className="flex justify-center py-6 border-b border-heal-line/40 dark:border-zinc-800/40">
                  <button
                    type="button"
                    onClick={() => setVisibleCount(prev => prev + PATIENTS_PAGE_SIZE)}
                    className="px-5 py-2.5 bg-[#f4f4f5] dark:bg-[#16181c] hover:bg-[#eff3f4] dark:hover:bg-[#2f3336] border border-[#eff3f4] dark:border-[#2f3336] text-[#0f1419] dark:text-[#e7e9ea] rounded-full text-xs font-bold transition-all cursor-pointer hover:border-heal-blue/30 dark:hover:border-heal-blue/30 active:scale-95 select-none"
                  >
                    Carregar Mais
                  </button>
                </div>
              )}

              {/* Mobile Table */}
              <div className="xl:hidden">
                {quickTableCard}
              </div>
            </div>
          ) : (
            <EmptyState
              icon={<Users className="h-7 w-7 text-heal-blue" />}
              title="Nenhum paciente encontrado"
              description="Cadastre seu primeiro paciente para testar leitura, edição, arquivamento e regras do Firestore."
              action={<Button type="button" onClick={openCreate}>Cadastrar paciente</Button>}
            />
          )}
        </div>
      </div>

      {/* Coluna Lateral Direita */}
      <aside className="hidden xl:block w-96 p-5 space-y-6 shrink-0 min-h-screen">
        {quickTableCard}
      </aside>

      <Modal open={modalOpen} title={editing ? 'Editar paciente' : 'Novo paciente'} onClose={() => setModalOpen(false)}>
        <PatientForm patient={editing} onSubmit={handleSubmit} onCancel={() => setModalOpen(false)} />
      </Modal>
    </div>
  );
}
