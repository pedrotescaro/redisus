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

      <div className="grid gap-6 xl:grid-cols-[380px_1fr]">
        <Card>
          <div className="flex flex-col items-center text-center">
            <UserAvatar
              name={displayName}
              src={photoURL}
              imageClassName="h-28 w-28 rounded-3xl object-cover ring-4 ring-heal-softBlue"
              fallbackClassName="flex h-28 w-28 items-center justify-center rounded-3xl bg-heal-softBlue text-3xl font-black text-heal-blue"
            />
            <h2 className="mt-5 text-2xl font-black text-heal-ink dark:text-white">{displayName}</h2>
            <p className="mt-1 text-sm text-heal-muted dark:text-zinc-400">{previewEmail}</p>
            <Link to="/profile/edit" className="mt-6 w-full">
              <Button className="w-full" icon={<Camera className="h-4 w-4" />}>
                Editar perfil
              </Button>
            </Link>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <div className="flex items-start gap-3">
              <BarChart3 className="mt-1 h-5 w-5 text-heal-blue" />
              <div className="w-full">
                <h3 className="font-black text-heal-ink dark:text-white">Métricas de performance</h3>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <Metric value={evaluationCount} label="Avaliações salvas" />
                  <Metric value={activePatients.length} label="Pacientes ativos" tone="teal" />
                  <Metric value="Firebase" label="Persistência ativa" tone="amber" />
                </div>
              </div>
            </div>
          </Card>

          <Card className="grid gap-4 md:grid-cols-2">
            <InfoBox label="Área de atuação" value={profile?.professionalArea || 'Não informado'} />
            <InfoBox label="Instituição ou clínica" value={profile?.clinicName || 'Não informado'} />
            <InfoBox label="Telefone" value={profile?.phone || 'Não informado'} />
            <InfoBox label="Tema" value={theme === 'dark' ? 'Escuro' : 'Claro'} />
          </Card>

          <Card>
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-1 h-5 w-5 text-heal-teal" />
              <div>
                <h3 className="font-black text-heal-ink dark:text-white">Provedores conectados</h3>
                <p className="mt-1 text-sm leading-6 text-heal-muted dark:text-zinc-400">
                  Os provedores vêm do Firebase Auth e são registrados no documento users/{'{uid}'}.
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {['password', 'google.com', 'microsoft.com', 'apple.com'].map(provider => (
                    <span
                      key={provider}
                      className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-bold ring-1 ${
                        providers.includes(provider)
                          ? 'bg-heal-tealSoft text-heal-teal ring-heal-teal/20'
                          : 'bg-slate-50 text-slate-400 ring-heal-line dark:bg-zinc-950 dark:ring-zinc-800'
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

          <Card className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue">
                {theme === 'dark' ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
              </div>
              <div>
                <p className="font-black text-heal-ink dark:text-white">Modo escuro</p>
                <p className="text-sm text-heal-muted dark:text-zinc-400">{theme === 'dark' ? 'Ativado' : 'Desativado'}</p>
              </div>
            </div>
            <Button type="button" variant="secondary" onClick={toggleTheme}>
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
    blue: 'text-heal-blue bg-heal-softBlue',
    teal: 'text-heal-teal bg-heal-tealSoft',
    amber: 'text-heal-warning bg-heal-warningSoft'
  };
  return (
    <div className={`rounded-2xl p-4 text-center ${colors[tone]}`}>
      <p className="text-2xl font-black">{value}</p>
      <p className="mt-1 text-xs font-bold">{label}</p>
    </div>
  );
}

function InfoBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-heal-line bg-heal-canvas p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <p className="text-xs font-bold uppercase tracking-wide text-heal-muted">{label}</p>
      <p className="mt-1 text-sm font-black text-heal-ink dark:text-white">{value}</p>
    </div>
  );
}

function ProfileAction({ icon, title, description, to }: { icon: ReactNode; title: string; description: string; to: string }) {
  return (
    <Link to={to}>
      <Card className="h-full transition hover:-translate-y-0.5 hover:border-heal-blue/40">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue">{icon}</div>
          <div>
            <p className="font-black text-heal-ink dark:text-white">{title}</p>
            <p className="mt-1 text-sm text-heal-muted dark:text-zinc-400">{description}</p>
          </div>
        </div>
      </Card>
    </Link>
  );
}
