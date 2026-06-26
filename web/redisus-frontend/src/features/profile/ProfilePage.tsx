import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Briefcase,
  Building2,
  Calendar,
  Camera,
  CheckCircle2,
  ChevronRight,
  LogOut,
  Mail,
  Moon,
  Phone,
  Settings,
  ShieldCheck,
  Sun,
  UserRound,
  Bell,
  Info
} from 'lucide-react';

import { useAuth } from '../../app/providers/AuthProvider';
import { useTheme } from '../../app/providers/ThemeProvider';
import { UserAvatar } from '../../components/profile/UserAvatar';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/Card';
import type { Patient } from '../../lib/types';
import { logout } from '../auth/authService';
import { listEvaluations } from '../evaluations/evaluationService';
import { subscribePatients } from '../patients/patientService';

const providerLabels: Record<string, string> = {
  password: 'E-mail/senha',
  'google.com': 'Google',
  'microsoft.com': 'Microsoft',
  'apple.com': 'Apple'
};

const formatJoinedDate = (dateStr?: string) => {
  if (!dateStr) return 'Membro do Heal+';
  const date = new Date(dateStr);
  const month = date.toLocaleDateString('pt-BR', { month: 'long' });
  const year = date.getFullYear();
  const capitalizedMonth = month.charAt(0).toUpperCase() + month.slice(1);
  return `Ingressou em ${capitalizedMonth} de ${year}`;
};

export function ProfilePage() {
  const { profile, user } = useAuth();
  const { theme, setTheme } = useTheme();
  const navigate = useNavigate();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [evaluationCount, setEvaluationCount] = useState(0);

  const displayName = profile?.displayName || user?.displayName || 'Profissional';
  const email = profile?.email || user?.email || '';
  const providers = profile?.providerIds?.length ? profile.providerIds : user?.providerData.map(p => p.providerId) || [];
  const showPhoto = profile?.settings?.showProfilePhoto ?? true;
  const photoURL = showPhoto ? profile?.photoURL || user?.photoURL : null;
  const hiddenEmail = profile?.settings?.hideEmailPreview;
  const previewEmail = hiddenEmail && email ? email.replace(/^(.{2}).*(@.*)$/, '$1***$2') : email;
  const activePatients = patients.filter(patient => !patient.archived);

  const [activeTab, setActiveTab] = useState<'visao-geral' | 'provedores' | 'atalhos'>('visao-geral');

  useEffect(() => {
    if (!user) return undefined;
    return subscribePatients(user.uid, next => setPatients(next));
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

  const toggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    if (user) {
      const updateSettings = async () => {
        const { updateSettings: update } = await import('./profileService');
        void update(user.uid, { theme: nextTheme });
      };
      void updateSettings();
    }
  };

  return (
    <div className="max-w-2xl w-full mx-auto bg-white dark:bg-[#0c0c0e] border border-heal-line/75 dark:border-zinc-800/80 rounded-2xl overflow-hidden shadow-sm min-h-[calc(100vh-140px)] flex flex-col antialiased">
      {/* Header (Twitter style: Back arrow + User name + stats) */}
      <div className="sticky top-0 z-30 bg-white/95 dark:bg-[#0c0c0e]/95 backdrop-blur-md border-b border-heal-line/60 dark:border-zinc-800/60 px-4 py-3 flex items-center gap-4">
        <button
          onClick={() => navigate(-1)}
          className="p-2 hover:bg-slate-50 dark:hover:bg-zinc-900 rounded-full transition-colors text-heal-ink dark:text-white cursor-pointer"
          title="Voltar"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-heal-ink dark:text-white text-base font-black tracking-tight leading-tight">
            {displayName}
          </h1>
          <p className="text-heal-muted dark:text-zinc-500 text-[10px] uppercase font-bold tracking-wider mt-0.5">
            {evaluationCount} {evaluationCount === 1 ? 'avaliação' : 'avaliações'}
          </p>
        </div>
      </div>

      {/* Profile Banner */}
      <div className="h-32 sm:h-40 bg-gradient-to-r from-heal-blue/20 via-heal-teal/10 to-transparent relative border-b border-heal-line/40 dark:border-zinc-800/40" />

      {/* Avatar and Edit Profile Button */}
      <div className="flex justify-between items-end px-4">
        <div className="-mt-12 sm:-mt-16 relative">
          <UserAvatar
            name={displayName}
            src={photoURL}
            imageClassName="w-24 h-24 sm:w-32 sm:h-32 rounded-full border-4 border-white dark:border-[#0c0c0e] object-cover bg-white dark:bg-[#0c0c0e] ring-2 ring-slate-800/10 animate-scale-in"
            fallbackClassName="flex w-24 h-24 sm:w-32 sm:h-32 items-center justify-center rounded-full border-4 border-white dark:border-[#0c0c0e] bg-heal-softBlue/60 text-2xl sm:text-3xl font-black text-heal-blue dark:bg-blue-950/40 animate-scale-in"
          />
        </div>
        <div className="pb-3">
          <Link to="/profile/edit">
            <button
              type="button"
              className="px-4.5 py-2 border border-heal-line dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:bg-slate-50 dark:hover:bg-zinc-850 text-heal-ink dark:text-white rounded-full text-xs font-black transition-all cursor-pointer active:scale-95 select-none"
            >
              Editar perfil
            </button>
          </Link>
        </div>
      </div>

      {/* User Bio and Info Section */}
      <div className="px-4 mt-3 space-y-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-heal-ink dark:text-white text-lg sm:text-xl font-black tracking-tight leading-none">
              {displayName}
            </h2>
            <span className="text-[10px] text-heal-teal bg-heal-tealSoft/40 dark:bg-emerald-950/40 border border-heal-teal/20 dark:border-emerald-950/60 px-2.5 py-0.5 rounded-full font-bold">
              Enfermagem
            </span>
          </div>
          <p className="text-xs text-heal-muted dark:text-zinc-500 font-semibold mt-1">@{previewEmail.split('@')[0]}</p>
        </div>

        {/* Bio Section */}
        <p className="text-xs text-heal-ink dark:text-zinc-300 leading-relaxed font-semibold">
          Profissional de saúde dedicado ao cuidado humanizado, evolução clínica e monitoramento de enfermagem inteligente no Heal+.
        </p>

        {/* Clinical Metadata */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[11px] font-bold text-heal-muted dark:text-zinc-400 uppercase tracking-wider">
          {profile?.clinicName && (
            <div className="flex items-center gap-1.5">
              <Building2 className="w-4 h-4 text-heal-blue" />
              <span>{profile.clinicName}</span>
            </div>
          )}
          {profile?.professionalArea && (
            <div className="flex items-center gap-1.5">
              <Briefcase className="w-4 h-4 text-heal-blue" />
              <span>{profile.professionalArea}</span>
            </div>
          )}
          <div className="flex items-center gap-1.5">
            <Calendar className="w-4 h-4 text-heal-blue" />
            <span>{formatJoinedDate(user?.metadata.creationTime)}</span>
          </div>
        </div>

        {/* Nursing Stats (Followers style adaptation) */}
        <div className="flex items-center gap-4 text-xs font-semibold pb-4">
          <span className="text-heal-muted dark:text-zinc-400">
            <strong className="text-heal-ink dark:text-white font-black">{activePatients.length}</strong>{' '}
            Pacientes ativos
          </span>
          <span className="text-heal-muted dark:text-zinc-400">
            <strong className="text-heal-ink dark:text-white font-black">{evaluationCount}</strong>{' '}
            Avaliações realizadas
          </span>
        </div>
      </div>

      {/* Tab Selector (Twitter/X style) */}
      <div className="border-b border-heal-line/60 dark:border-zinc-800/60 flex select-none">
        {[
          { id: 'visao-geral', label: 'Visão geral' },
          { id: 'provedores', label: 'Provedores conectados' },
          { id: 'atalhos', label: 'Preferências & Atalhos' }
        ].map((tab) => {
          const isSelected = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id as any)}
              className={`relative flex-1 py-3.5 text-xs font-bold transition-colors cursor-pointer text-center ${
                isSelected
                  ? 'text-heal-blue dark:text-blue-400 font-extrabold'
                  : 'text-heal-muted dark:text-zinc-400 hover:text-heal-ink dark:hover:text-white hover:bg-slate-50/50 dark:hover:bg-zinc-900/20'
              }`}
            >
              {tab.label}
              {isSelected && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-heal-blue rounded-full" />
              )}
            </button>
          );
        })}
      </div>

      {/* Conditional Content Rendering */}
      <div className="flex-grow p-4 sm:p-6 bg-slate-50/20 dark:bg-zinc-950/25">
        {activeTab === 'visao-geral' && (
          <div className="space-y-6 animate-fade-in">
            <div className="grid gap-4 sm:grid-cols-3">
              <Metric value={evaluationCount} label="Avaliações" />
              <Metric value={activePatients.length} label="Ativos" tone="teal" />
              <Metric value="Seguro" label="Firebase" tone="amber" />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <InfoBox label="Área de atuação" value={profile?.professionalArea || 'Não informado'} icon={<Briefcase className="w-4 h-4 text-heal-muted" />} />
              <InfoBox label="Instituição ou clínica" value={profile?.clinicName || 'Não informado'} icon={<Building2 className="w-4 h-4 text-heal-muted" />} />
              <InfoBox label="Telefone" value={profile?.phone || 'Não informado'} icon={<Phone className="w-4 h-4 text-heal-muted" />} />
              <InfoBox label="Modo Escuro" value={theme === 'dark' ? 'Ativado' : 'Desativado'} icon={theme === 'dark' ? <Moon className="w-4 h-4 text-heal-muted" /> : <Sun className="w-4 h-4 text-heal-muted" />} />
            </div>
          </div>
        )}

        {activeTab === 'provedores' && (
          <div className="space-y-4 animate-fade-in">
            <div>
              <h3 className="font-black text-sm text-heal-ink dark:text-white">Provedores conectados</h3>
              <p className="mt-1 text-xs text-heal-muted dark:text-zinc-500 leading-relaxed">
                Os provedores de autenticação integrados ao seu perfil de acesso via Firebase Auth.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {['password', 'google.com', 'microsoft.com', 'apple.com'].map(provider => {
                const isConnected = providers.includes(provider);
                return (
                  <div
                    key={provider}
                    className={`flex items-center justify-between rounded-xl p-4 border text-xs font-bold ${
                      isConnected
                        ? 'bg-heal-tealSoft/10 text-heal-teal border-heal-teal/20 dark:bg-emerald-950/25 dark:text-emerald-300 dark:border-emerald-950/40'
                        : 'bg-white text-slate-400 border-heal-line dark:bg-zinc-900 dark:border-zinc-800/60'
                    }`}
                  >
                    <span className="flex items-center gap-2">
                      {isConnected ? <CheckCircle2 className="h-4 w-4 shrink-0 text-heal-teal" /> : <div className="w-4 h-4 rounded-full border border-slate-300 dark:border-zinc-700" />}
                      {providerLabels[provider]}
                    </span>
                    {isConnected && (
                      <span className="text-[9px] px-2 py-0.5 rounded-full bg-heal-teal/10 font-bold uppercase tracking-wider">
                        Ativo
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {activeTab === 'atalhos' && (
          <div className="space-y-6 animate-fade-in">
            <div className="grid gap-3 md:grid-cols-2">
              <ProfileAction icon={<Bell className="h-5 w-5" />} title="Notificações" description="Push, e-mail e lembretes" to="/notifications" />
              <ProfileAction icon={<ShieldCheck className="h-5 w-5" />} title="Privacidade" description="Previews e dados exibidos" to="/privacy" />
              <ProfileAction icon={<Settings className="h-5 w-5" />} title="Configurações" description="Tema e preferências rápidas" to="/settings" />
              <ProfileAction icon={<Info className="h-5 w-5" />} title="Sobre o app" description="Versão e proposta acadêmica" to="/about" />
            </div>

            <div className="border-t border-heal-line/60 dark:border-zinc-800/60 pt-6">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e] p-5 rounded-xl">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-heal-softBlue/60 text-heal-blue dark:bg-blue-950/40">
                    {theme === 'dark' ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
                  </div>
                  <div>
                    <p className="font-black text-sm text-heal-ink dark:text-white leading-tight">Alternar Tema</p>
                    <p className="text-xs text-heal-muted dark:text-zinc-500">{theme === 'dark' ? 'Modo Escuro' : 'Modo Claro'}</p>
                  </div>
                </div>
                <Button type="button" size="sm" variant="secondary" onClick={toggleTheme}>
                  {theme === 'dark' ? 'Usar claro' : 'Usar escuro'}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Metric({ value, label, tone = 'blue' }: { value: string | number; label: string; tone?: 'blue' | 'teal' | 'amber' }) {
  const colors = {
    blue: 'text-heal-blue border-heal-blue/20 bg-heal-softBlue/10 dark:bg-blue-950/20 dark:border-blue-950/40',
    teal: 'text-heal-teal border-heal-teal/20 bg-heal-tealSoft/10 dark:bg-emerald-950/20 dark:border-emerald-950/40',
    amber: 'text-heal-warning border-heal-warning/20 bg-heal-warningSoft/10 dark:bg-amber-950/20 dark:border-amber-950/40'
  };
  return (
    <div className={`rounded-xl border p-4 text-center ${colors[tone]}`}>
      <p className="text-xl font-black">{value}</p>
      <p className="mt-1 text-[10px] font-extrabold uppercase tracking-wider opacity-90">{label}</p>
    </div>
  );
}

function InfoBox({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-heal-line/75 bg-white dark:border-zinc-800/80 dark:bg-zinc-900/40 p-4 flex items-start gap-3">
      {icon && <div className="mt-0.5">{icon}</div>}
      <div className="min-w-0">
        <p className="text-[10px] font-extrabold uppercase tracking-wider text-heal-muted">{label}</p>
        <p className="mt-1 text-xs font-black text-heal-ink dark:text-white truncate">{value}</p>
      </div>
    </div>
  );
}

function ProfileAction({ icon, title, description, to }: { icon: React.ReactNode; title: string; description: string; to: string }) {
  return (
    <Link to={to} className="block h-full">
      <Card hover className="h-full border border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e] p-4 rounded-xl">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-heal-softBlue/50 text-heal-blue dark:bg-blue-950/30">{icon}</div>
          <div>
            <p className="font-black text-sm text-heal-ink dark:text-white leading-tight">{title}</p>
            <p className="mt-1 text-xs text-heal-muted dark:text-zinc-400 leading-normal">{description}</p>
          </div>
        </div>
      </Card>
    </Link>
  );
}

