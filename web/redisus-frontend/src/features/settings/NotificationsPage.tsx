import { useAuth } from '../../app/providers/AuthProvider';
import { Card } from '../../components/ui/Card';
import { updateSettings } from '../profile/profileService';

export function NotificationsPage() {
  const { user, profile } = useAuth();
  const settings = profile?.settings;

  const toggle = (key: string, value: boolean) => {
    if (user) void updateSettings(user.uid, { [key]: value });
  };

  return (
    <Card className="mx-auto max-w-2xl">
      <h2 className="text-2xl font-black text-heal-ink dark:text-white">Notificacoes</h2>
      <div className="mt-5 space-y-4">
        <Toggle label="Notificacoes ligadas" checked={settings?.notificationsEnabled ?? true} onChange={value => toggle('notificationsEnabled', value)} />
        <Toggle label="E-mails de acompanhamento" checked={settings?.emailNotificationsEnabled ?? true} onChange={value => toggle('emailNotificationsEnabled', value)} />
        <Toggle label="Lembretes da agenda" checked={settings?.agendaRemindersEnabled ?? true} onChange={value => toggle('agendaRemindersEnabled', value)} />
      </div>
    </Card>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex items-center justify-between rounded-lg border border-heal-line p-4 dark:border-zinc-800">
      <span className="font-semibold text-heal-ink dark:text-white">{label}</span>
      <input type="checkbox" className="h-5 w-5 rounded border-heal-line text-heal-blue" checked={checked} onChange={event => onChange(event.target.checked)} />
    </label>
  );
}
