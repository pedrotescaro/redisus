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

  // Render appointments widget to avoid duplication
  const appointmentsWidget = (
    <Card className="border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e]">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-heal-blue">Agenda</p>
          <h2 className="mt-1 text-lg font-black text-heal-ink dark:text-white">Próximos atendimentos</h2>
        </div>
        <Link
          to="/agenda"
          className="inline-flex h-8 items-center justify-center rounded-xl border border-heal-line bg-white px-3 text-xs font-bold text-heal-ink hover:bg-slate-50 transition-colors dark:border-zinc-800 dark:bg-zinc-900 dark:text-white dark:hover:bg-zinc-800"
        >
          Ver tudo
        </Link>
      </div>

      <div className="mt-5 space-y-3">
        {upcoming.length ? (
          upcoming.map(item => (
            <div key={item.id} className="rounded-xl border border-heal-line/60 bg-heal-canvas/40 p-3.5 transition hover:border-heal-blue/30 dark:border-zinc-800/60 dark:bg-zinc-950/40">
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-sm font-bold text-heal-ink dark:text-white">{item.patientName}</p>
                <Badge tone={item.status === 'Confirmado' ? 'green' : item.status === 'Cancelado' ? 'red' : 'amber'}>{item.status}</Badge>
              </div>
              <p className="mt-1.5 text-xs text-heal-muted dark:text-zinc-400">
                {formatDate(item.date)} às {item.time} · {item.type}
              </p>
            </div>
          ))
        ) : (
          <div className="rounded-xl border border-dashed border-heal-line/80 bg-heal-canvas/30 p-6 text-center dark:border-zinc-800/80 dark:bg-zinc-950/30">
            <CalendarDays className="mx-auto h-6 w-6 text-heal-blue opacity-85" />
            <p className="mt-3 text-sm font-bold text-heal-ink dark:text-white">Nenhum atendimento futuro</p>
            <p className="mt-1 text-xs text-heal-muted dark:text-zinc-500">Crie consultas na agenda para aparecerem aqui.</p>
          </div>
        )}
      </div>
    </Card>
  );

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-6 xl:items-start">
      {/* Left Column: Main content */}
      <div className="space-y-6">
        <Link
          to="/chat"
          className="flex min-h-14 items-center gap-3 rounded-2xl border border-heal-line/75 bg-white px-4 shadow-sm transition hover:border-heal-blue/40 hover:bg-heal-softBlue/30 dark:border-zinc-800/85 dark:bg-[#0c0c0e] dark:hover:bg-[#131316]/50"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-heal-softBlue/60 text-heal-blue dark:bg-blue-950/45">
            <Sparkles className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-black text-heal-ink dark:text-white">Pergunte ou pesquise</p>
            <p className="truncate text-xs font-semibold text-heal-muted dark:text-zinc-400">Pacientes, agenda, avaliações e retornos já salvos</p>
          </div>
          <Search className="h-4.5 w-4.5 text-heal-muted" />
        </Link>

        <section className="overflow-hidden rounded-2xl border border-heal-line/75 bg-white p-6 shadow-sm dark:border-zinc-800/85 dark:bg-[#0c0c0e] lg:p-8">
          <div className="grid gap-6 lg:grid-cols-[1fr_auto] lg:items-center">
            <div>
              <Badge tone="blue">Dr. {firstName}</Badge>
              <h1 className="mt-4 text-2xl font-black leading-tight tracking-tight text-heal-ink dark:text-white sm:text-3xl lg:text-4xl">
                Pronto para acompanhar?
              </h1>
              <p className="mt-3 text-sm leading-6 text-heal-muted dark:text-zinc-400">
                Avalie feridas, consulte pacientes cadastrados no Firebase, controle a agenda e analise dados com inteligência artificial.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                {quickActions.map(action => (
                  <Link
                    key={action.to}
                    to={action.to}
                    className="inline-flex h-10 items-center gap-2 rounded-full border border-heal-line/80 bg-heal-canvas/40 px-4 text-xs font-bold text-heal-ink transition hover:border-heal-blue/50 hover:bg-heal-softBlue/30 dark:border-zinc-800/80 dark:bg-zinc-950/40 dark:text-white"
                  >
                    <span className={`flex h-6 w-6 items-center justify-center rounded-full ${action.tone}`}>
                      <action.icon className="h-3.5 w-3.5" />
                    </span>
                    {action.label}
                  </Link>
                ))}
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:w-[320px] xl:w-auto shrink-0">
              <MetricCard label="Pacientes ativos" value={activePatients.length} icon={<Users className="h-4.5 w-4.5" />} tone="blue" />
              <MetricCard label="Avaliações" value={evaluationCount} icon={<ClipboardPlus className="h-4.5 w-4.5" />} tone="green" />
              <MetricCard label="Agenda futura" value={upcoming.length} icon={<CalendarDays className="h-4.5 w-4.5" />} tone="amber" />
              <MetricCard label="Arquivados" value={archivedPatients} icon={<FileText className="h-4.5 w-4.5" />} tone="slate" />
            </div>
          </div>
        </section>

        <section className="grid gap-4 sm:grid-cols-2">
          {shortcutCards.map(item => (
            <Link key={item.to} to={item.to} className="group rounded-2xl border border-heal-line/75 bg-white p-5 transition hover:border-heal-blue/40 hover:bg-slate-50/20 dark:border-zinc-800/85 dark:bg-[#0c0c0e] dark:hover:bg-[#131316]/30">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-heal-softBlue/40 text-heal-blue dark:bg-blue-950/30">
                <item.icon className="h-5 w-5" />
              </div>
              <h2 className="mt-4 text-sm font-black text-heal-ink dark:text-white">{item.title}</h2>
              <p className="mt-1.5 text-xs leading-5 text-heal-muted dark:text-zinc-400">{item.description}</p>
            </Link>
          ))}
        </section>

        {/* Mobile appointments widget */}
        <div className="xl:hidden">
          {appointmentsWidget}
        </div>
      </div>

      {/* Right Column: Sticky Sidebar widget */}
      <aside className="sticky top-20 hidden xl:block space-y-6">
        {appointmentsWidget}
      </aside>
    </div>
  );
}

function MetricCard({ label, value, icon, tone }: { label: string; value: number; icon: ReactNode; tone: 'blue' | 'green' | 'amber' | 'slate' }) {
  const styles = {
    blue: 'text-heal-blue',
    green: 'text-heal-teal',
    amber: 'text-heal-warning',
    slate: 'text-heal-muted'
  };

  return (
    <div className="rounded-xl border border-heal-line/75 bg-white p-4 dark:border-zinc-800/80 dark:bg-[#0c0c0e]">
      <div className={`flex h-9 w-9 items-center justify-center rounded-xl bg-heal-canvas/40 dark:bg-zinc-950/40 ${styles[tone]}`}>{icon}</div>
      <p className="mt-3 text-2xl font-black text-heal-ink dark:text-white leading-none">{value}</p>
      <p className="mt-1.5 text-xs font-bold text-heal-muted dark:text-zinc-500 leading-none">{label}</p>
    </div>
  );
}
