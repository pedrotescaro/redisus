import { BarChart3, Bell, Camera, CheckCircle2, Info, LogOut, Moon, Settings, ShieldCheck, Sun } from 'lucide-react';
import { useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

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
import { updateSettings } from './profileService';

const providerLabels: Record<string, string> = {
  password: 'E-mail/senha',
  'google.com': 'Google',
  'microsoft.com': 'Microsoft',
  'apple.com': 'Apple'
};

export function ProfilePage() {
  const { profile, user } = useAuth();
  const { theme, setTheme } = useTheme();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [evaluationCount, setEvaluationCount] = useState(0);
  const displayName = profile?.displayName || user?.displayName || 'Profissional';
  const email = profile?.email || user?.email || '';
  const providers = profile?.providerIds?.length ? profile.providerIds : user?.providerData.map(provider => provider.providerId) || [];
  const showPhoto = profile?.settings?.showProfilePhoto ?? true;
  const photoURL = showPhoto ? profile?.photoURL || user?.photoURL : null;
  const hiddenEmail = profile?.settings?.hideEmailPreview;
  const previewEmail = hiddenEmail && email ? email.replace(/^(.{2}).*(@.*)$/, '$1***$2') : email;
  const activePatients = patients.filter(patient => !patient.archived);

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
    if (user) void updateSettings(user.uid, { theme: nextTheme });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Perfil"
        title="Conta profissional"
        description="Gerencie dados, foto, provedores conectados, privacidade e preferências do Heal+."
        action={
          <Button type="button" variant="secondary" icon={<LogOut className="h-4 w-4" />} onClick={() => void logout()}>
            Sair
          </Button>
        }
      />

      <div className="grid gap-6 xl:grid-cols-[340px_1fr]">
        <Card className="border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e] h-fit">
          <div className="flex flex-col items-center text-center">
            <UserAvatar
              name={displayName}
              src={photoURL}
              imageClassName="h-24 w-24 rounded-2xl object-cover ring-2 ring-heal-blue/30"
              fallbackClassName="flex h-24 w-24 items-center justify-center rounded-2xl bg-heal-softBlue/60 text-2xl font-black text-heal-blue dark:bg-blue-950/40"
            />
            <h2 className="mt-4 text-xl font-black text-heal-ink dark:text-white leading-tight">{displayName}</h2>
            <p className="mt-1 text-xs text-heal-muted dark:text-zinc-500 font-medium">{previewEmail}</p>
            <Link to="/profile/edit" className="mt-5 w-full">
              <Button className="w-full" size="sm" icon={<Camera className="h-4 w-4" />}>
                Editar perfil
              </Button>
            </Link>
          </div>
        </Card>

        <div className="space-y-4">
          <Card className="border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e] p-5">
            <div className="flex items-start gap-3">
              <BarChart3 className="mt-1 h-5 w-5 text-heal-blue shrink-0" />
              <div className="w-full">
                <h3 className="font-black text-sm text-heal-ink dark:text-white">Métricas de performance</h3>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <Metric value={evaluationCount} label="Avaliações" />
                  <Metric value={activePatients.length} label="Ativos" tone="teal" />
                  <Metric value="Firebase" label="Persistência" tone="amber" />
                </div>
              </div>
            </div>
          </Card>

          <Card className="grid gap-4 md:grid-cols-2 border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e] p-5">
            <InfoBox label="Área de atuação" value={profile?.professionalArea || 'Não informado'} />
            <InfoBox label="Instituição ou clínica" value={profile?.clinicName || 'Não informado'} />
            <InfoBox label="Telefone" value={profile?.phone || 'Não informado'} />
            <InfoBox label="Tema" value={theme === 'dark' ? 'Escuro' : 'Claro'} />
          </Card>

          <Card className="border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e] p-5">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-1 h-5 w-5 text-heal-teal shrink-0" />
              <div>
                <h3 className="font-black text-sm text-heal-ink dark:text-white">Provedores conectados</h3>
                <p className="mt-1 text-xs leading-5 text-heal-muted dark:text-zinc-500">
                  Os provedores vêm do Firebase Auth e são registrados no documento users/{'{uid}'}.
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {['password', 'google.com', 'microsoft.com', 'apple.com'].map(provider => (
                    <span
                      key={provider}
                      className={`inline-flex items-center gap-2 rounded-xl px-3 py-1.5 text-xs font-bold ring-1 ${
                        providers.includes(provider)
                          ? 'bg-heal-tealSoft/50 text-heal-teal ring-heal-teal/20 dark:bg-emerald-950/40 dark:text-emerald-300'
                          : 'bg-slate-50/50 text-slate-400 ring-heal-line/60 dark:bg-zinc-950/40 dark:ring-zinc-800/60'
                      }`}
                    >
                      {providers.includes(provider) ? <CheckCircle2 className="h-3.5 w-3.5" /> : null}
                      {providerLabels[provider]}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </Card>

          <div className="grid gap-3 md:grid-cols-2">
            <ProfileAction icon={<Bell className="h-5 w-5" />} title="Notificações" description="Push, e-mail e lembretes" to="/notifications" />
            <ProfileAction icon={<ShieldCheck className="h-5 w-5" />} title="Privacidade" description="Previews e dados exibidos" to="/privacy" />
            <ProfileAction icon={<Settings className="h-5 w-5" />} title="Configurações" description="Tema e preferências rápidas" to="/settings" />
            <ProfileAction icon={<Info className="h-5 w-5" />} title="Sobre o app" description="Versão e proposta acadêmica" to="/about" />
          </div>

          <Card className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e] p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-heal-softBlue/60 text-heal-blue dark:bg-blue-950/40">
                {theme === 'dark' ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
              </div>
              <div>
                <p className="font-black text-sm text-heal-ink dark:text-white leading-tight">Modo escuro</p>
                <p className="text-xs text-heal-muted dark:text-zinc-500">{theme === 'dark' ? 'Ativado' : 'Desativado'}</p>
              </div>
            </div>
            <Button type="button" size="sm" variant="secondary" onClick={toggleTheme}>
              {theme === 'dark' ? 'Usar claro' : 'Usar escuro'}
            </Button>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Metric({ value, label, tone = 'blue' }: { value: string | number; label: string; tone?: 'blue' | 'teal' | 'amber' }) {
  const colors = {
    blue: 'text-heal-blue border-heal-blue/20 bg-heal-softBlue/20 dark:bg-blue-950/20',
    teal: 'text-heal-teal border-heal-teal/20 bg-heal-tealSoft/20 dark:bg-emerald-950/20',
    amber: 'text-heal-warning border-heal-warning/20 bg-heal-warningSoft/20 dark:bg-amber-950/20'
  };
  return (
    <div className={`rounded-xl border p-4 text-center ${colors[tone]}`}>
      <p className="text-xl font-black">{value}</p>
      <p className="mt-1 text-[10px] font-bold uppercase tracking-wider opacity-95">{label}</p>
    </div>
  );
}

function InfoBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-heal-line/75 bg-heal-canvas/40 p-4 dark:border-zinc-800/80 dark:bg-zinc-950/40">
      <p className="text-[10px] font-bold uppercase tracking-wider text-heal-muted">{label}</p>
      <p className="mt-1 text-sm font-black text-heal-ink dark:text-white truncate">{value}</p>
    </div>
  );
}

function ProfileAction({ icon, title, description, to }: { icon: ReactNode; title: string; description: string; to: string }) {
  return (
    <Link to={to}>
      <Card hover className="h-full border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e] p-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-heal-softBlue/50 text-heal-blue dark:bg-blue-950/30">{icon}</div>
          <div>
            <p className="font-black text-sm text-heal-ink dark:text-white leading-tight">{title}</p>
            <p className="mt-1 text-xs text-heal-muted dark:text-zinc-400">{description}</p>
          </div>
        </div>
      </Card>
    </Link>
  );
}
