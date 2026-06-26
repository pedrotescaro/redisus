import { useAuth } from '../../app/providers/AuthProvider';
import { PageHeader } from '../../components/ui/PageHeader';
import { updateSettings } from '../profile/profileService';

export function NotificationsPage() {
  const { user, profile } = useAuth();
  const settings = profile?.settings;

  const toggle = (key: string, value: boolean) => {
    if (user) void updateSettings(user.uid, { [key]: value });
  };

  return (
    <div className="flex flex-col xl:flex-row min-h-screen min-w-0 bg-white dark:bg-[#0c0c0e]">
      {/* Coluna Central */}
      <div className="flex-grow max-w-2xl w-full border-r border-heal-line dark:border-zinc-800/60 min-h-screen flex flex-col min-w-0">
        <PageHeader showBack title="Notificações" description="Gerencie suas preferências de alertas" />

        <div className="p-4 sm:p-6 space-y-3">
          <Toggle label="Notificações ligadas" checked={settings?.notificationsEnabled ?? true} onChange={value => toggle('notificationsEnabled', value)} />
          <Toggle label="E-mails de acompanhamento" checked={settings?.emailNotificationsEnabled ?? true} onChange={value => toggle('emailNotificationsEnabled', value)} />
          <Toggle label="Lembretes da agenda" checked={settings?.agendaRemindersEnabled ?? true} onChange={value => toggle('agendaRemindersEnabled', value)} />
        </div>
      </div>
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
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
