import { CalendarDays, Edit, Plus, Trash2, ArrowLeft, ArrowRight } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { useAuth } from '../../app/providers/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { LoadingState } from '../../components/ui/LoadingState';
import { Modal } from '../../components/ui/Modal';
import { PageHeader } from '../../components/ui/PageHeader';
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

  // Calendar states
  const [calMonth, setCalMonth] = useState(new Date().getMonth());
  const [calYear, setCalYear] = useState(new Date().getFullYear());
  const [selectedCalDate, setSelectedCalDate] = useState<string | null>(null);

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
    let list = appointments;
    if (selectedCalDate) {
      list = list.filter(item => item.date === selectedCalDate);
      return list;
    }
    if (view === 'lista') return list;
    const today = todayISO();
    if (view === 'semana') return list.filter(item => item.date >= today).slice(0, 7);
    return list.filter(item => item.date.slice(0, 7) === today.slice(0, 7));
  }, [appointments, view, selectedCalDate]);

  const appointmentDates = useMemo(() => {
    return new Set(appointments.map(a => a.date));
  }, [appointments]);

  const handleSubmit = async (values: AppointmentFormValues) => {
    if (!user) return;
    if (editing) await updateAppointment(user.uid, editing.id, values);
    else await createAppointment(user.uid, values);
    setModalOpen(false);
    setEditing(null);
  };

  // Calendar Helpers
  const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
  const firstDayIndex = new Date(calYear, calMonth, 1).getDay();
  const prevMonthDays = new Date(calYear, calMonth, 0).getDate();
  
  const cells: { day: number; dateStr: string; isCurrentMonth: boolean }[] = [];
  
  for (let i = firstDayIndex - 1; i >= 0; i--) {
    const d = prevMonthDays - i;
    const m = calMonth === 0 ? 11 : calMonth - 1;
    const y = calMonth === 0 ? calYear - 1 : calYear;
    cells.push({
      day: d,
      dateStr: `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`,
      isCurrentMonth: false
    });
  }
  
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({
      day: d,
      dateStr: `${calYear}-${String(calMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`,
      isCurrentMonth: true
    });
  }
  
  const remaining = 42 - cells.length;
  for (let d = 1; d <= remaining; d++) {
    const m = calMonth === 11 ? 0 : calMonth + 1;
    const y = calMonth === 11 ? calYear + 1 : calYear;
    cells.push({
      day: d,
      dateStr: `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`,
      isCurrentMonth: false
    });
  }

  const nextMonth = () => {
    if (calMonth === 11) {
      setCalMonth(0);
      setCalYear(prev => prev + 1);
    } else {
      setCalMonth(prev => prev + 1);
    }
  };
  
  const prevMonth = () => {
    if (calMonth === 0) {
      setCalMonth(11);
      setCalYear(prev => prev - 1);
    } else {
      setCalMonth(prev => prev - 1);
    }
  };

  if (loading) return <LoadingState label="Carregando agenda..." />;

  return (
    <div className="flex flex-col xl:flex-row min-h-screen min-w-0 bg-white dark:bg-[#0c0c0e]">
      {/* Coluna Central */}
      <div className="flex-grow max-w-5xl w-full border-r border-heal-line dark:border-zinc-800/60 min-h-screen flex flex-col min-w-0">
        <PageHeader
          title="Agenda"
          description="Controle de atendimentos clínicos"
          action={
            <Button icon={<Plus className="h-4 w-4" />} onClick={() => { setEditing(null); setModalOpen(true); }}>
              Novo atendimento
            </Button>
          }
        />

        {/* View Switcher Tabs */}
        <div className="flex w-full border-b border-heal-line/60 dark:border-zinc-800/60 bg-transparent select-none">
          {(['lista', 'semana', 'mes'] as const).map(item => {
            const active = view === item;
            const label = item === 'mes' ? 'Mês' : item[0].toUpperCase() + item.slice(1);
            return (
              <button
                key={item}
                type="button"
                className={`relative flex-1 py-3 text-xs font-bold transition-colors text-center cursor-pointer ${
                  active ? 'text-heal-ink dark:text-white' : 'text-heal-muted hover:text-heal-ink dark:hover:text-white'
                }`}
                onClick={() => {
                  setView(item);
                  setSelectedCalDate(null); // Clear calendar filter when switching tabs
                }}
              >
                {label}
                {active && <div className="absolute bottom-0 left-1/4 right-1/4 h-0.5 rounded-full bg-heal-blue" />}
              </button>
            );
          })}
        </div>

        {/* Filter indication */}
        {selectedCalDate && (
          <div className="px-4 sm:px-6 pt-4 flex items-center justify-between">
            <p className="text-xs font-bold text-heal-muted">
              Mostrando atendimentos para: <span className="text-heal-blue font-black">{formatDate(selectedCalDate)}</span>
            </p>
            <button
              onClick={() => setSelectedCalDate(null)}
              className="text-xs font-bold text-red-500 hover:underline cursor-pointer border-0 bg-transparent"
            >
              Limpar Filtro
            </button>
          </div>
        )}

        {/* Page Content */}
        <div className="p-4 sm:p-6 flex-grow space-y-4">
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
        </div>
      </div>

      {/* Coluna Lateral Direita: Twitter-style Calendar */}
      <aside className="hidden xl:block w-96 p-5 shrink-0 min-h-screen">
        <div className="sticky top-6 space-y-6">
          <Card className="p-4 border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e]">
            {/* Header: Month & Navigation */}
            <div className="flex items-center justify-between pb-3 border-b border-heal-line/60 dark:border-zinc-800/60">
              <h3 className="text-sm font-bold text-heal-ink dark:text-white capitalize">
                {new Date(calYear, calMonth).toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' })}
              </h3>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={prevMonth}
                  className="p-1.5 hover:bg-heal-canvas/60 dark:hover:bg-zinc-900 rounded-lg text-heal-muted hover:text-heal-ink dark:hover:text-white transition-colors cursor-pointer border-0 bg-transparent"
                >
                  <ArrowLeft className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={nextMonth}
                  className="p-1.5 hover:bg-heal-canvas/60 dark:hover:bg-zinc-900 rounded-lg text-heal-muted hover:text-heal-ink dark:hover:text-white transition-colors cursor-pointer border-0 bg-transparent"
                >
                  <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Weekdays */}
            <div className="grid grid-cols-7 gap-1 mt-3 text-center text-[10px] font-black text-heal-muted uppercase tracking-wider">
              {['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'].map(d => (
                <div key={d} className="py-1">{d}</div>
              ))}
            </div>

            {/* Days Grid */}
            <div className="grid grid-cols-7 gap-1 mt-1">
              {cells.map((cell, idx) => {
                const hasAppts = appointmentDates.has(cell.dateStr);
                const isSelected = selectedCalDate === cell.dateStr;
                const isToday = todayISO() === cell.dateStr;
                
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setSelectedCalDate(isSelected ? null : cell.dateStr)}
                    className={`relative aspect-square flex flex-col items-center justify-center text-xs font-bold rounded-full transition-all cursor-pointer border-0 bg-transparent hover:bg-heal-softBlue/55 dark:hover:bg-blue-900/30 ${
                      isSelected 
                        ? 'bg-heal-blue text-white hover:bg-heal-blueDark font-black'
                        : isToday
                        ? 'border border-heal-blue text-heal-blue font-black'
                        : cell.isCurrentMonth
                        ? 'text-heal-ink dark:text-zinc-300'
                        : 'text-slate-300 dark:text-zinc-700 font-normal'
                    }`}
                  >
                    <span>{cell.day}</span>
                    {hasAppts && !isSelected && (
                      <span className={`absolute bottom-1 w-1 h-1 rounded-full ${isToday ? 'bg-heal-blue' : 'bg-heal-blue/70 dark:bg-blue-400'}`} />
                    )}
                  </button>
                );
              })}
            </div>

            {/* Calendar Controls */}
            {selectedCalDate && (
              <div className="mt-4 pt-3 border-t border-heal-line/60 dark:border-zinc-800/60 flex items-center justify-between text-xs">
                <span className="font-semibold text-heal-muted">Filtrando: {formatDate(selectedCalDate)}</span>
                <button
                  type="button"
                  onClick={() => setSelectedCalDate(null)}
                  className="font-bold text-heal-blue hover:underline cursor-pointer border-0 bg-transparent"
                >
                  Ver Todos
                </button>
              </div>
            )}
          </Card>
        </div>
      </aside>

      <Modal open={modalOpen} title={editing ? 'Editar atendimento' : 'Novo atendimento'} onClose={() => setModalOpen(false)}>
        <AppointmentForm patients={patients} appointment={editing} defaultPatientId={searchParams.get('patientId') || undefined} onSubmit={handleSubmit} onCancel={() => setModalOpen(false)} />
      </Modal>
    </div>
  );
}
