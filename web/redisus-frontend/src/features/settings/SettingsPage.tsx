import { Bell, Building2, ChevronRight, Info, LogOut, Mail, Moon, ShieldCheck, Sun, UserRound } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../../app/providers/AuthProvider';
import { useTheme } from '../../app/providers/ThemeProvider';
import { Button } from '../../components/ui/button';
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
  const email = profile?.email || user?.email || 'e-mail não informado';

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
      <section className="overflow-hidden rounded-2xl border border-heal-line/75 bg-white dark:border-zinc-800/80 dark:bg-[#0c0c0e]">
        <div className="grid gap-6 p-6 lg:grid-cols-[1fr_320px] lg:p-8">
          <div className="flex min-w-0 items-center gap-4">
            <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-heal-softBlue/60 text-heal-blue dark:bg-blue-950/40 ring-2 ring-heal-blue/20">
              {profile?.photoURL ? <img src={profile.photoURL} alt="" className="h-full w-full object-cover" /> : <UserRound className="h-9 w-9" />}
            </div>
            <div className="min-w-0">
              <p className="text-xs font-black uppercase tracking-[0.18em] text-heal-blue">Perfil</p>
              <h1 className="mt-1 truncate text-2xl font-black tracking-tight text-heal-ink dark:text-white">{displayName}</h1>
              <div className="mt-2.5 flex flex-wrap gap-3 text-xs font-semibold text-heal-muted dark:text-zinc-400">
                <span className="inline-flex items-center gap-1.5"><Mail className="h-4 w-4 text-heal-muted" />{email}</span>
                {profile?.clinicName ? <span className="inline-flex items-center gap-1.5"><Building2 className="h-4 w-4 text-heal-muted" />{profile.clinicName}</span> : null}
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
        <Card className="border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e] p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-heal-blue">Conta</p>
          <div className="mt-4 divide-y divide-heal-line/60 dark:divide-zinc-800/60">
            <SettingsLink
              to="/profile/edit"
              icon={<UserRound className="h-5 w-5" />}
              iconClassName="bg-blue-50 text-heal-blue dark:bg-blue-950/40"
              title="Editar perfil"
              description="Nome, área profissional, clínica e telefone"
            />
            <SettingsLink
              to="/notifications"
              icon={<Bell className="h-5 w-5" />}
              iconClassName="bg-emerald-50 text-heal-teal dark:bg-emerald-950/40"
              title="Notificações"
              description={settings?.notificationsEnabled === false ? 'Avisos pausados' : 'Alertas e lembretes ativos'}
            />
            <SettingsLink
              to="/privacy"
              icon={<ShieldCheck className="h-5 w-5" />}
              iconClassName="bg-amber-50 text-heal-warning dark:bg-amber-950/40"
              title="Privacidade"
              description="Previews, foto de perfil e separação por UID"
            />
            <SettingsLink
              to="/about"
              icon={<Info className="h-5 w-5" />}
              iconClassName="bg-pink-50 text-pink-500 dark:bg-pink-950/40"
              title="Sobre App"
              description="Versão, arquitetura e proposta acadêmica"
            />
          </div>
        </Card>

        <div className="space-y-4">
          <Card className="border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e] p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-heal-softBlue/60 text-heal-blue dark:bg-blue-950/40">
                {isDark ? <Moon className="h-5.5 w-5.5" /> : <Sun className="h-5.5 w-5.5" />}
              </div>
              <div>
                <h2 className="text-sm font-black text-heal-ink dark:text-white leading-tight">Aparência</h2>
                <p className="text-xs font-semibold text-heal-muted dark:text-zinc-500">Sincronizada no seu perfil</p>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-1 rounded-xl border border-heal-line/60 bg-heal-canvas/40 p-1 dark:border-zinc-800/60 dark:bg-[#131316]/50 select-none">
              <button
                type="button"
                className={`rounded-lg px-3 py-2 text-xs font-bold transition cursor-pointer ${!isDark ? 'bg-white text-heal-blue shadow-sm dark:bg-zinc-800 dark:text-white' : 'text-heal-muted hover:text-heal-ink dark:hover:text-white'}`}
                onClick={() => setThemePreference('light')}
              >
                Claro
              </button>
              <button
                type="button"
                className={`rounded-lg px-3 py-2 text-xs font-bold transition cursor-pointer ${isDark ? 'bg-white text-heal-blue shadow-sm dark:bg-zinc-800 dark:text-white' : 'text-heal-muted hover:text-heal-ink dark:hover:text-white'}`}
                onClick={() => setThemePreference('dark')}
              >
                Escuro
              </button>
            </div>
          </Card>

          <Card className="border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e] p-5">
            <h2 className="text-sm font-black text-heal-ink dark:text-white mb-4">Preferências rápidas</h2>
            <div className="space-y-2.5">
              <ToggleRow label="Notificações gerais" checked={settings?.notificationsEnabled ?? true} onChange={value => saveSetting('notificationsEnabled', value)} />
              <ToggleRow label="Mostrar foto de perfil" checked={settings?.showProfilePhoto ?? true} onChange={value => saveSetting('showProfilePhoto', value)} />
              <ToggleRow label="Ocultar e-mail no topo" checked={settings?.hideEmailPreview ?? false} onChange={value => saveSetting('hideEmailPreview', value)} />
              <ToggleRow label="Lembretes da agenda" checked={settings?.agendaRemindersEnabled ?? true} onChange={value => saveSetting('agendaRemindersEnabled', value)} />
            </div>
          </Card>

          <Button type="button" size="sm" variant="danger" className="w-full justify-center" icon={<LogOut className="h-4 w-4" />} onClick={() => void handleLogout()}>
            Sair da Conta
          </Button>
        </div>
      </div>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-heal-line/75 bg-heal-canvas/40 p-4 dark:border-zinc-800/80 dark:bg-zinc-950/40">
      <p className="text-[10px] font-black uppercase tracking-[0.14em] text-heal-muted">{label}</p>
      <p className="mt-1.5 text-base font-black text-heal-ink dark:text-white leading-none">{value}</p>
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
  // Strip off heavy background color from iconClassName, use custom flat styled wrapper
  const flatIconClass = iconClassName
    .replace('bg-blue-50', 'bg-blue-500/10 text-heal-blue')
    .replace('bg-emerald-50', 'bg-emerald-500/10 text-heal-teal')
    .replace('bg-amber-50', 'bg-amber-500/10 text-heal-warning')
    .replace('bg-pink-50', 'bg-pink-500/10 text-pink-500')
    .replace('dark:bg-blue-950/40', 'dark:bg-blue-500/10')
    .replace('dark:bg-emerald-950/40', 'dark:bg-emerald-500/10')
    .replace('dark:bg-amber-950/40', 'dark:bg-amber-500/10')
    .replace('dark:bg-pink-950/40', 'dark:bg-pink-500/10');

  return (
    <Link to={to} className="flex items-center gap-4 py-3.5 hover:bg-slate-50/50 dark:hover:bg-zinc-900/20 px-2 rounded-xl transition-all duration-150">
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${flatIconClass}`}>{icon}</div>
      <div className="min-w-0 flex-1">
        <h3 className="text-xs font-bold text-heal-ink dark:text-white leading-tight">{title}</h3>
        <p className="mt-1 truncate text-xs text-heal-muted dark:text-zinc-500">{description}</p>
      </div>
      <ChevronRight className="h-4.5 w-4.5 shrink-0 text-heal-muted opacity-80" />
    </Link>
  );
}

function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4 rounded-xl border border-heal-line/75 bg-heal-canvas/40 p-3.5 dark:border-zinc-800/80 dark:bg-zinc-950/40 hover:bg-heal-canvas/60 dark:hover:bg-zinc-900/30 transition-all select-none">
      <span className="text-xs font-bold text-heal-ink dark:text-white">{label}</span>
      <span className={`relative h-6 w-11 rounded-full transition ${checked ? 'bg-heal-blue' : 'bg-slate-300 dark:bg-zinc-850'}`}>
        <input type="checkbox" className="sr-only" checked={checked} onChange={event => onChange(event.target.checked)} />
        <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition ${checked ? 'left-5.5' : 'left-0.5'}`} />
      </span>
    </label>
  );
}
