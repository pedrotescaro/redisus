import { Bot, CalendarDays, ClipboardPlus, FileText, Search, Sparkles, SplitSquareHorizontal, Users } from 'lucide-react';
import type { ReactNode } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '../../app/providers/AuthProvider';
import { Badge } from '../../components/ui/Badge';
import { Card } from '../../components/ui/Card';
import { LoadingState } from '../../components/ui/LoadingState';
import { formatDate, todayISO } from '../../lib/date';
import type { Appointment, Patient } from '../../lib/types';
import { subscribeAppointments } from '../agenda/agendaService';
import { listEvaluations } from '../evaluations/evaluationService';
import { subscribePatients } from '../patients/patientService';

const quickActions = [
  { to: '/evaluations/new', label: 'Avaliação', icon: ClipboardPlus, tone: 'bg-blue-50 text-heal-blue dark:bg-blue-950/40' },
  { to: '/patients', label: 'Pacientes', icon: Users, tone: 'bg-emerald-50 text-heal-teal dark:bg-emerald-950/40' },
  { to: '/reports', label: 'Relatório', icon: FileText, tone: 'bg-amber-50 text-heal-warning dark:bg-amber-950/40' },
  { to: '/reports/compare', label: 'Comparar', icon: SplitSquareHorizontal, tone: 'bg-pink-50 text-pink-500 dark:bg-pink-950/40' }
];

const shortcutCards = [
  { to: '/evaluations/new', title: 'Nova avaliação', description: 'Registrar TIMERS, imagem e ROI.', icon: ClipboardPlus },
  { to: '/reports/compare', title: 'Comparar evolução', description: 'Antes e agora no modelo visual.', icon: SplitSquareHorizontal },
  { to: '/agenda', title: 'Agenda clínica', description: 'Criar, editar e excluir atendimentos.', icon: CalendarDays },
  { to: '/chat', title: 'Assistente', description: 'Pesquisar dados já salvos.', icon: Bot }
];

export function DashboardPage() {
  const { user, profile } = useAuth();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [evaluationCount, setEvaluationCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return undefined;
    const unsubscribePatients = subscribePatients(
      user.uid,
      next => {
        setPatients(next);
        setLoading(false);
      },
      () => setLoading(false)
    );
    const unsubscribeAppointments = subscribeAppointments(user.uid, setAppointments);
    return () => {
      unsubscribePatients();
      unsubscribeAppointments();
    };
  }, [user]);

  useEffect(() => {
    if (!user || !patients.length) {
      setEvaluationCount(0);
      return;
    }
    void Promise.all(patients.map(patient => listEvaluations(user.uid, patient.id))).then(groups => {
      setEvaluationCount(groups.reduce((sum, group) => sum + group.length, 0));
    });
  }, [patients, user]);

  const activePatients = patients.filter(patient => !patient.archived);
  const archivedPatients = patients.length - activePatients.length;
  const upcoming = useMemo(
    () =>
      appointments
        .filter(item => item.date >= todayISO() && item.status !== 'Cancelado')
        .sort((a, b) => a.date.localeCompare(b.date) || a.time.localeCompare(b.time))
        .slice(0, 5),
    [appointments]
  );
  const firstName = (profile?.displayName || user?.displayName || 'Profissional').split(' ')[0];

  if (loading) return <LoadingState label="Carregando dashboard..." />;

  return (
    <div className="space-y-6">
      <Link
        to="/chat"
        className="flex min-h-14 items-center gap-3 rounded-2xl border border-heal-line bg-white px-4 shadow-sm transition hover:border-heal-blue/50 hover:bg-heal-softBlue dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-blue-950/30"
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue dark:bg-blue-950/40">
          <Sparkles className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-black text-heal-ink dark:text-white">Pergunte ou pesquise</p>
          <p className="truncate text-xs font-semibold text-heal-muted dark:text-zinc-400">Pacientes, agenda, avaliações e retornos já salvos</p>
        </div>
        <Search className="h-5 w-5 text-heal-muted" />
      </Link>

      <section className="overflow-hidden rounded-[1.75rem] border border-heal-line bg-white p-6 shadow-soft dark:border-zinc-800 dark:bg-zinc-900 lg:p-8">
        <div className="grid gap-6 xl:grid-cols-[1fr_420px] xl:items-center">
          <div>
            <Badge tone="blue">Olá, Dr. {firstName}.</Badge>
            <h1 className="mt-4 max-w-3xl text-3xl font-black leading-tight tracking-tight text-heal-ink dark:text-white md:text-5xl">
              Pronto para continuar o acompanhamento?
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-heal-muted dark:text-zinc-400 md:text-base">
              O fluxo principal fica aqui: avaliar feridas, consultar pacientes, acompanhar agenda e gerar relatórios.
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              {quickActions.map(action => (
                <Link
                  key={action.to}
                  to={action.to}
                  className="inline-flex h-11 items-center gap-2 rounded-full border border-heal-line bg-heal-canvas px-4 text-sm font-black text-heal-ink transition hover:border-heal-blue/50 hover:bg-heal-softBlue dark:border-zinc-800 dark:bg-zinc-950 dark:text-white"
                >
                  <span className={`flex h-7 w-7 items-center justify-center rounded-full ${action.tone}`}>
                    <action.icon className="h-4 w-4" />
                  </span>
                  {action.label}
                </Link>
              ))}
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <MetricCard label="Pacientes ativos" value={activePatients.length} icon={<Users className="h-5 w-5" />} tone="blue" />
            <MetricCard label="Avaliações" value={evaluationCount} icon={<ClipboardPlus className="h-5 w-5" />} tone="green" />
            <MetricCard label="Agenda futura" value={upcoming.length} icon={<CalendarDays className="h-5 w-5" />} tone="amber" />
            <MetricCard label="Arquivados" value={archivedPatients} icon={<FileText className="h-5 w-5" />} tone="slate" />
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1fr_420px]">
        <div className="grid gap-4 sm:grid-cols-2">
          {shortcutCards.map(item => (
            <Link key={item.to} to={item.to} className="group rounded-2xl border border-heal-line bg-white p-5 shadow-soft transition hover:-translate-y-0.5 hover:border-heal-blue/50 dark:border-zinc-800 dark:bg-zinc-900">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue dark:bg-blue-950/40">
                <item.icon className="h-5 w-5" />
              </div>
              <h2 className="mt-4 text-base font-black text-heal-ink dark:text-white">{item.title}</h2>
              <p className="mt-2 text-sm leading-6 text-heal-muted dark:text-zinc-400">{item.description}</p>
            </Link>
          ))}
        </div>

        <Card>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.18em] text-heal-teal">Agenda</p>
              <h2 className="mt-1 text-xl font-black text-heal-ink dark:text-white">Próximos atendimentos</h2>
            </div>
            <Link
              to="/agenda"
              className="inline-flex h-8 items-center justify-center rounded-lg border border-heal-line bg-white px-3 text-xs font-semibold text-heal-ink transition hover:border-heal-blue/40 hover:bg-slate-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white dark:hover:bg-zinc-800"
            >
              Ver agenda
            </Link>
          </div>

          <div className="mt-5 space-y-3">
            {upcoming.length ? (
              upcoming.map(item => (
                <div key={item.id} className="rounded-2xl border border-heal-line bg-heal-canvas p-4 dark:border-zinc-800 dark:bg-zinc-950">
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-sm font-black text-heal-ink dark:text-white">{item.patientName}</p>
                    <Badge tone={item.status === 'Confirmado' ? 'green' : item.status === 'Cancelado' ? 'red' : 'amber'}>{item.status}</Badge>
                  </div>
                  <p className="mt-1 text-sm text-heal-muted dark:text-zinc-400">
                    {formatDate(item.date)} as {item.time} - {item.type}
                  </p>
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-dashed border-heal-line bg-heal-canvas p-6 text-center dark:border-zinc-800 dark:bg-zinc-950">
                <CalendarDays className="mx-auto h-7 w-7 text-heal-blue" />
                <p className="mt-3 text-sm font-bold text-heal-ink dark:text-white">Nenhum atendimento futuro</p>
                <p className="mt-1 text-xs leading-5 text-heal-muted dark:text-zinc-400">Crie consultas na agenda para aparecerem aqui.</p>
              </div>
            )}
          </div>
        </Card>
      </section>
    </div>
  );
}

function MetricCard({ label, value, icon, tone }: { label: string; value: number; icon: ReactNode; tone: 'blue' | 'green' | 'amber' | 'slate' }) {
  const styles = {
    blue: 'bg-blue-50 text-heal-blue dark:bg-blue-950/40',
    green: 'bg-emerald-50 text-heal-teal dark:bg-emerald-950/40',
    amber: 'bg-amber-50 text-heal-warning dark:bg-amber-950/40',
    slate: 'bg-slate-100 text-slate-600 dark:bg-zinc-800 dark:text-zinc-300'
  };

  return (
    <div className="rounded-2xl border border-heal-line bg-heal-canvas p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className={`flex h-11 w-11 items-center justify-center rounded-2xl ${styles[tone]}`}>{icon}</div>
      <p className="mt-4 text-3xl font-black text-heal-ink dark:text-white">{value}</p>
      <p className="mt-1 text-sm font-bold text-heal-muted dark:text-zinc-400">{label}</p>
    </div>
  );
}
