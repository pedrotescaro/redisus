import { Bell, Building2, ChevronRight, Info, LogOut, Mail, Moon, ShieldCheck, Sun, UserRound } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../../app/providers/AuthProvider';
import { useTheme } from '../../app/providers/ThemeProvider';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { logout } from '../auth/authService';
import { updateSettings } from '../profile/profileService';

export function SettingsPage() {
  const { user, profile } = useAuth();
  const { theme, setTheme } = useTheme();
  const navigate = useNavigate();
  const settings = profile?.settings;
  const isDark = theme === 'dark';
  const displayName = profile?.displayName || user?.displayName || 'Profissional Heal+';
  const email = profile?.email || user?.email || 'email nao informado';

  const saveSetting = (key: string, value: boolean | string) => {
    if (user) void updateSettings(user.uid, { [key]: value });
  };

  const setThemePreference = (nextTheme: 'light' | 'dark') => {
    setTheme(nextTheme);
    saveSetting('theme', nextTheme);
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-[1.75rem] border border-heal-line bg-white shadow-soft dark:border-zinc-800 dark:bg-zinc-900">
        <div className="grid gap-6 p-6 lg:grid-cols-[1fr_320px] lg:p-8">
          <div className="flex min-w-0 items-center gap-4">
            <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-3xl bg-heal-softBlue text-heal-blue dark:bg-blue-950/40">
              {profile?.photoURL ? <img src={profile.photoURL} alt="" className="h-full w-full object-cover" /> : <UserRound className="h-9 w-9" />}
            </div>
            <div className="min-w-0">
              <p className="text-xs font-black uppercase tracking-[0.18em] text-heal-teal">Perfil</p>
              <h1 className="mt-1 truncate text-3xl font-black tracking-tight text-heal-ink dark:text-white">{displayName}</h1>
              <div className="mt-3 flex flex-wrap gap-3 text-sm font-semibold text-heal-muted dark:text-zinc-400">
                <span className="inline-flex items-center gap-1.5"><Mail className="h-4 w-4" />{email}</span>
                {profile?.clinicName ? <span className="inline-flex items-center gap-1.5"><Building2 className="h-4 w-4" />{profile.clinicName}</span> : null}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <MiniMetric label="Tema" value={isDark ? 'Escuro' : 'Claro'} />
            <MiniMetric label="Avisos" value={settings?.notificationsEnabled === false ? 'Pausados' : 'Ativos'} />
          </div>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <Card>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-heal-teal">Conta</p>
          <div className="mt-4 divide-y divide-heal-line dark:divide-zinc-800">
            <SettingsLink
              to="/profile/edit"
              icon={<UserRound className="h-5 w-5" />}
              iconClassName="bg-blue-50 text-heal-blue dark:bg-blue-950/40"
              title="Editar perfil"
              description="Nome, area profissional, clinica e telefone"
            />
            <SettingsLink
              to="/notifications"
              icon={<Bell className="h-5 w-5" />}
              iconClassName="bg-emerald-50 text-heal-teal dark:bg-emerald-950/40"
              title="Notificacoes"
              description={settings?.notificationsEnabled === false ? 'Avisos pausados' : 'Alertas e lembretes ativos'}
            />
            <SettingsLink
              to="/privacy"
              icon={<ShieldCheck className="h-5 w-5" />}
              iconClassName="bg-amber-50 text-heal-warning dark:bg-amber-950/40"
              title="Privacidade"
              description="Previews, foto de perfil e separacao por UID"
            />
            <SettingsLink
              to="/about"
              icon={<Info className="h-5 w-5" />}
              iconClassName="bg-pink-50 text-pink-500 dark:bg-pink-950/40"
              title="Sobre App"
              description="Versao, arquitetura e proposta academica"
            />
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue dark:bg-blue-950/40">
                {isDark ? <Moon className="h-6 w-6" /> : <Sun className="h-6 w-6" />}
              </div>
              <div>
                <h2 className="text-lg font-black text-heal-ink dark:text-white">Aparencia</h2>
                <p className="text-sm font-semibold text-heal-muted dark:text-zinc-400">Sincronizada no seu perfil</p>
              </div>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-2 rounded-2xl border border-heal-line bg-heal-canvas p-1 dark:border-zinc-800 dark:bg-zinc-950">
              <button
                type="button"
                className={`rounded-xl px-3 py-3 text-sm font-black transition ${!isDark ? 'bg-white text-heal-blue shadow-sm dark:bg-zinc-900' : 'text-heal-muted hover:text-heal-ink dark:hover:text-white'}`}
                onClick={() => setThemePreference('light')}
              >
                Claro
              </button>
              <button
                type="button"
                className={`rounded-xl px-3 py-3 text-sm font-black transition ${isDark ? 'bg-white text-heal-blue shadow-sm dark:bg-zinc-900' : 'text-heal-muted hover:text-heal-ink dark:hover:text-white'}`}
                onClick={() => setThemePreference('dark')}
              >
                Escuro
              </button>
            </div>
          </Card>

          <Card>
            <h2 className="text-lg font-black text-heal-ink dark:text-white">Preferencias rapidas</h2>
            <div className="mt-4 space-y-3">
              <ToggleRow label="Notificacoes gerais" checked={settings?.notificationsEnabled ?? true} onChange={value => saveSetting('notificationsEnabled', value)} />
              <ToggleRow label="Mostrar foto de perfil" checked={settings?.showProfilePhoto ?? true} onChange={value => saveSetting('showProfilePhoto', value)} />
              <ToggleRow label="Ocultar e-mail no topo" checked={settings?.hideEmailPreview ?? false} onChange={value => saveSetting('hideEmailPreview', value)} />
              <ToggleRow label="Lembretes da agenda" checked={settings?.agendaRemindersEnabled ?? true} onChange={value => saveSetting('agendaRemindersEnabled', value)} />
            </div>
          </Card>

          <Button type="button" variant="danger" className="w-full" icon={<LogOut className="h-4 w-4" />} onClick={() => void handleLogout()}>
            Sair
          </Button>
        </div>
      </div>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-heal-line bg-heal-canvas p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <p className="text-xs font-black uppercase tracking-[0.14em] text-heal-muted">{label}</p>
      <p className="mt-2 text-lg font-black text-heal-ink dark:text-white">{value}</p>
    </div>
  );
}

function SettingsLink({
  to,
  icon,
  iconClassName,
  title,
  description
}: {
  to: string;
  icon: ReactNode;
  iconClassName: string;
  title: string;
  description: string;
}) {
  return (
    <Link to={to} className="flex items-center gap-4 py-4">
      <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${iconClassName}`}>{icon}</div>
      <div className="min-w-0 flex-1">
        <h3 className="text-sm font-black text-heal-ink dark:text-white">{title}</h3>
        <p className="mt-1 truncate text-sm font-semibold text-heal-muted dark:text-zinc-400">{description}</p>
      </div>
      <ChevronRight className="h-5 w-5 shrink-0 text-heal-muted" />
    </Link>
  );
}

function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4 rounded-2xl border border-heal-line bg-heal-canvas p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <span className="text-sm font-bold text-heal-ink dark:text-white">{label}</span>
      <span className={`relative h-7 w-12 rounded-full transition ${checked ? 'bg-heal-blue' : 'bg-slate-300 dark:bg-zinc-700'}`}>
        <input type="checkbox" className="sr-only" checked={checked} onChange={event => onChange(event.target.checked)} />
        <span className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow-sm transition ${checked ? 'left-6' : 'left-1'}`} />
      </span>
    </label>
  );
}
