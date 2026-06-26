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
import { PageHeader } from '../../components/ui/PageHeader';
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
    <div className="flex flex-col xl:flex-row min-h-screen min-w-0 bg-white dark:bg-[#0c0c0e]">
      <div className="flex-grow max-w-2xl w-full border-r border-heal-line dark:border-zinc-800/60 min-h-screen flex flex-col min-w-0 antialiased">
        <PageHeader title="Perfil Profissional" description="Identidade clínica e credenciais de acesso" />

        <div className="p-4 sm:p-6 space-y-6">
          
          <div className="flex flex-col sm:flex-row gap-5 items-start sm:items-center justify-between py-2">
            <div className="flex items-center gap-4 select-none">
              <UserAvatar
                name={displayName}
                src={photoURL}
                imageClassName="w-16 h-16 rounded-full object-cover ring-2 ring-heal-blue/20"
                fallbackClassName="flex w-16 h-16 items-center justify-center rounded-full bg-heal-softBlue/60 text-xl font-black text-heal-blue dark:bg-blue-950/40"
              />
              <div className="space-y-1">
                <div className="flex items-center gap-2.5">
                  <h2 className="text-base font-black text-heal-ink dark:text-white tracking-tight">
                    {displayName}
                  </h2>
                  <span className="text-[9px] text-heal-teal bg-heal-tealSoft/30 dark:bg-emerald-950/30 border border-heal-teal/20 dark:border-emerald-950/50 px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">
                    Enfermagem
                  </span>
                </div>
                <p className="text-xs text-heal-muted dark:text-zinc-500 font-semibold">{email}</p>
              </div>
            </div>

            <Link to="/profile/edit" className="w-full sm:w-auto shrink-0 select-none">
              <button
                type="button"
                className="w-full sm:w-auto px-5 py-2 bg-heal-blue hover:bg-blue-600 active:scale-95 text-white rounded-full text-xs font-bold transition-all cursor-pointer"
              >
                Editar dados
              </button>
            </Link>
          </div>

          <div className="grid gap-3 grid-cols-1 sm:grid-cols-[2fr_1fr_1fr]">
            <div className="rounded-2xl border border-heal-line/75 dark:border-zinc-800 bg-white dark:bg-[#0c0c0e] p-5 space-y-3.5 select-none flex flex-col justify-center shadow-sm">
              <h3 className="text-[10px] font-bold text-heal-muted dark:text-zinc-500 uppercase tracking-wider">Detalhamento Clínico</h3>
              <div className="space-y-2.5 text-xs font-semibold text-heal-ink dark:text-zinc-300">
                <div className="flex items-center gap-2">
                  <Briefcase className="w-4 h-4 text-heal-blue shrink-0" />
                  <span className="truncate">Enfermagem</span>
                </div>
                <div className="flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-heal-blue shrink-0" />
                  <span>{formatJoinedDate(user?.metadata.creationTime)}</span>
                </div>
              </div>
            </div>

            <Metric value={activePatients.length} label="Ativos" tone="blue" />
            <Metric value={evaluationCount} label="Avaliações" tone="green" />
          </div>

          <div className="border-b border-heal-line/60 dark:border-zinc-800/60 flex select-none mt-6">
            {[
              { id: 'visao-geral', label: 'Visão Geral' },
              { id: 'provedores', label: 'Provedores de Acesso' },
              { id: 'atalhos', label: 'Preferências & Atalhos' }
            ].map((tab) => {
              const isSelected = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`py-3.5 px-4 text-xs font-bold transition-all cursor-pointer relative ${
                    isSelected
                      ? 'text-heal-blue dark:text-blue-400 font-extrabold'
                      : 'text-heal-muted dark:text-zinc-500 hover:text-heal-ink dark:hover:text-white'
                  }`}
                >
                  {tab.label}
                  {isSelected && (
                    <div className="absolute bottom-0 left-4 right-4 h-[2px] bg-heal-blue rounded-full" />
                  )}
                </button>
              );
            })}
          </div>

          <div className="pt-2">
            {activeTab === 'visao-geral' && (
              <div className="space-y-4 animate-fade-in">
                <div className="grid gap-3 sm:grid-cols-2">
                  <InfoBox label="Área de atuação" value={profile?.professionalArea || 'Não informado'} icon={<Briefcase className="w-4.5 h-4.5" />} />
                  <InfoBox label="Instituição ou clínica" value={profile?.clinicName || 'Não informado'} icon={<Building2 className="w-4.5 h-4.5" />} />
                  <InfoBox label="Telefone" value={profile?.phone || 'Não informado'} icon={<Phone className="w-4.5 h-4.5" />} />
                  <InfoBox label="Modo Escuro" value={theme === 'dark' ? 'Ativado' : 'Desativado'} icon={theme === 'dark' ? <Moon className="w-4.5 h-4.5" /> : <Sun className="w-4.5 h-4.5" />} />
                </div>
              </div>
            )}

            {activeTab === 'provedores' && (
              <div className="space-y-4 animate-fade-in">
                <div className="space-y-1 select-none">
                  <h3 className="font-bold text-xs text-heal-ink dark:text-white">Provedores Conectados</h3>
                  <p className="text-[10px] text-heal-muted dark:text-zinc-500 leading-relaxed font-semibold">
                    Os métodos de autenticação vinculados ao seu perfil de acesso via Firebase Auth.
                  </p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  {['password', 'google.com', 'microsoft.com', 'apple.com'].map(provider => {
                    const isConnected = providers.includes(provider);
                    return (
                      <div
                        key={provider}
                        className={`flex items-center justify-between rounded-2xl p-4 border text-xs font-bold shadow-sm ${
                          isConnected
                            ? 'bg-heal-tealSoft/10 text-heal-teal border-heal-teal/20 dark:bg-emerald-950/25 dark:text-emerald-300 dark:border-emerald-950/40'
                            : 'bg-white text-slate-400 border-heal-line dark:bg-[#0c0c0e] dark:border-zinc-800/60'
                        }`}
                      >
                        <span className="flex items-center gap-2 select-none">
                          {isConnected ? <CheckCircle2 className="h-4 w-4 shrink-0 text-heal-teal" /> : <div className="w-4 h-4 rounded-full border border-slate-300 dark:border-zinc-700" />}
                          {providerLabels[provider]}
                        </span>
                        {isConnected && (
                          <span className="text-[9px] px-2 py-0.5 rounded-full bg-heal-teal/10 font-bold uppercase tracking-wider select-none">
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
              <div className="space-y-5 animate-fade-in">
                <div className="grid gap-3 md:grid-cols-2">
                  <ProfileAction icon={<Bell className="h-4.5 w-4.5" />} title="Notificações" description="Push, e-mail e lembretes" to="/notifications" />
                  <ProfileAction icon={<ShieldCheck className="h-4.5 w-4.5" />} title="Privacidade" description="Previews e dados exibidos" to="/privacy" />
                  <ProfileAction icon={<Settings className="h-4.5 w-4.5" />} title="Configurações" description="Tema e preferências rápidas" to="/settings" />
                  <ProfileAction icon={<Info className="h-4.5 w-4.5" />} title="Sobre o app" description="Versão e proposta acadêmica" to="/about" />
                </div>

                <div className="border-t border-heal-line/60 dark:border-zinc-800/60 pt-5">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border border-heal-line/75 dark:border-zinc-800 bg-white dark:bg-[#0c0c0e] p-4.5 rounded-2xl shadow-sm">
                    <div className="flex items-center gap-3 select-none">
                      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-heal-softBlue/60 text-heal-blue dark:bg-blue-950/40">
                        {theme === 'dark' ? <Moon className="h-4.5 w-4.5" /> : <Sun className="h-4.5 w-4.5" />}
                      </div>
                      <div>
                        <p className="font-bold text-xs text-heal-ink dark:text-white leading-tight">Alternar Tema</p>
                        <p className="text-[10px] text-heal-muted dark:text-zinc-500 font-semibold">{theme === 'dark' ? 'Modo Escuro' : 'Modo Claro'}</p>
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
      </div>
    </div>
  );
}

function Metric({ value, label, tone = 'blue' }: { value: string | number; label: string; tone?: 'blue' | 'green' }) {
  const colors = {
    blue: 'text-heal-blue border-heal-line/75 dark:border-zinc-800 bg-white dark:bg-[#0c0c0e]',
    green: 'text-heal-teal border-heal-line/75 dark:border-zinc-800 bg-white dark:bg-[#0c0c0e]'
  };
  return (
    <div className={`rounded-2xl border p-5 flex flex-col items-center justify-center text-center select-none shadow-sm ${colors[tone]}`}>
      <p className="text-2xl font-black">{value}</p>
      <p className="mt-1 text-[9px] font-extrabold uppercase tracking-wider opacity-90">{label}</p>
    </div>
  );
}

function InfoBox({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-heal-line/75 bg-white dark:border-zinc-800/80 dark:bg-[#141417] p-4.5 flex items-center gap-3.5 shadow-sm select-none">
      {icon && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-heal-softBlue/50 text-heal-blue dark:bg-blue-950/30 dark:text-blue-400">
          {icon}
        </div>
      )}
      <div className="min-w-0">
        <p className="text-[9px] font-extrabold uppercase tracking-wider text-heal-muted dark:text-zinc-500">{label}</p>
        <p className="mt-1 text-xs font-black text-heal-ink dark:text-white truncate">{value}</p>
      </div>
    </div>
  );
}

function ProfileAction({ icon, title, description, to }: { icon: React.ReactNode; title: string; description: string; to: string }) {
  return (
    <Link to={to} className="block h-full">
      <Card hover className="h-full border border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e] p-4 rounded-2xl shadow-sm">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-heal-softBlue/50 text-heal-blue dark:bg-blue-950/30">{icon}</div>
          <div>
            <p className="font-black text-xs text-heal-ink dark:text-white leading-tight">{title}</p>
            <p className="mt-1 text-[11px] text-heal-muted dark:text-zinc-400 leading-normal">{description}</p>
          </div>
        </div>
      </Card>
    </Link>
  );
}
