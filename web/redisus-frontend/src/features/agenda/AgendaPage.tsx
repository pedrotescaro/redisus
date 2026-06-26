import { CalendarDays, Edit, Plus, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { useAuth } from '../../app/providers/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { LoadingState } from '../../components/ui/LoadingState';
import { Modal } from '../../components/ui/Modal';
import { formatDate, todayISO } from '../../lib/date';
import type { Appointment, Patient } from '../../lib/types';
import { subscribePatients } from '../patients/patientService';
import { AppointmentForm } from './AppointmentForm';
import { createAppointment, deleteAppointment, subscribeAppointments, updateAppointment, type AppointmentFormValues } from './agendaService';

export function AgendaPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Appointment | null>(null);
  const [view, setView] = useState<'lista' | 'semana' | 'mes'>('lista');
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    if (!user) return undefined;
    const unPatients = subscribePatients(user.uid, next => setPatients(next.filter(patient => !patient.archived)));
    const unAppointments = subscribeAppointments(
      user.uid,
      next => {
        setAppointments(next);
        setLoadError('');
        setLoading(false);
      },
      () => {
        setLoadError('Não foi possível carregar a agenda agora. Tente novamente em instantes.');
        setLoading(false);
      }
    );
    return () => {
      unPatients();
      unAppointments();
    };
  }, [user]);

  const visibleAppointments = useMemo(() => {
    if (view === 'lista') return appointments;
    const today = todayISO();
    if (view === 'semana') return appointments.filter(item => item.date >= today).slice(0, 7);
    return appointments.filter(item => item.date.slice(0, 7) === today.slice(0, 7));
  }, [appointments, view]);

  const handleSubmit = async (values: AppointmentFormValues) => {
    if (!user) return;
    if (editing) await updateAppointment(user.uid, editing.id, values);
    else await createAppointment(user.uid, values);
    setModalOpen(false);
    setEditing(null);
  };

  if (loading) return <LoadingState label="Carregando agenda..." />;

  return (
    <div className="space-y-5">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h2 className="text-2xl font-black text-heal-ink dark:text-white">Agenda</h2>
          <p className="text-sm text-slate-500 dark:text-zinc-400">Atendimentos em users/uid/appointments.</p>
        </div>
        <Button icon={<Plus className="h-4 w-4" />} onClick={() => { setEditing(null); setModalOpen(true); }}>
          Novo atendimento
        </Button>
      </div>

      <div className="flex w-full border-b border-heal-line/60 dark:border-zinc-800/60 bg-transparent select-none mb-4">
        {(['lista', 'semana', 'mes'] as const).map(item => {
          const active = view === item;
          const label = item === 'mes' ? 'Mês' : item[0].toUpperCase() + item.slice(1);
          return (
            <button
              key={item}
              type="button"
              className={`relative flex-1 py-3 text-xs font-bold transition-colors text-center ${
                active ? 'text-heal-ink dark:text-white' : 'text-heal-muted hover:text-heal-ink dark:hover:text-white'
              }`}
              onClick={() => setView(item)}
            >
              {label}
              {active && <div className="absolute bottom-0 left-1/4 right-1/4 h-0.5 rounded-full bg-heal-blue" />}
            </button>
          );
        })}
      </div>

      {loadError ? <EmptyState title="Erro ao carregar agenda" description={loadError} /> : null}

      {!loadError && visibleAppointments.length ? (
        <div className="grid gap-3">
          {visibleAppointments.map(appointment => (
            <Card key={appointment.id} className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e] p-4">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-heal-softBlue/60 text-heal-blue dark:bg-blue-950/40">
                  <CalendarDays className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-bold text-sm text-heal-ink dark:text-white">{appointment.patientName}</h3>
                    <Badge tone={appointment.status === 'Confirmado' || appointment.status === 'Realizado' ? 'green' : appointment.status === 'Cancelado' ? 'red' : 'amber'}>
                      {appointment.status}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-slate-500 dark:text-zinc-400">{formatDate(appointment.date)} às {appointment.time} · {appointment.type}</p>
                  {appointment.notes ? <p className="mt-2 text-xs leading-5 text-slate-600 dark:text-zinc-300">{appointment.notes}</p> : null}
                </div>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="secondary" icon={<Edit className="h-3.5 w-3.5" />} onClick={() => { setEditing(appointment); setModalOpen(true); }}>Editar</Button>
                <Button
                  size="sm"
                  variant="danger"
                  icon={<Trash2 className="h-3.5 w-3.5" />}
                  onClick={() => {
                    if (user && window.confirm('Excluir este atendimento da agenda?')) void deleteAppointment(user.uid, appointment.id);
                  }}
                >
                  Excluir
                </Button>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState title="Agenda vazia" description="Cadastre atendimentos para validar CRUD e próximos eventos no dashboard." />
      )}

      <Modal open={modalOpen} title={editing ? 'Editar atendimento' : 'Novo atendimento'} onClose={() => setModalOpen(false)}>
        <AppointmentForm patients={patients} appointment={editing} defaultPatientId={searchParams.get('patientId') || undefined} onSubmit={handleSubmit} onCancel={() => setModalOpen(false)} />
      </Modal>
    </div>
  );
}
