import { useAuth } from '../../app/providers/AuthProvider';
import { Card } from '../../components/ui/Card';
import { updateSettings } from '../profile/profileService';

export function PrivacyPage() {
  const { user, profile } = useAuth();
  const settings = profile?.settings;

  const toggle = (key: string, value: boolean) => {
    if (user) void updateSettings(user.uid, { [key]: value });
  };

  return (
    <Card className="mx-auto max-w-3xl">
      <h2 className="text-2xl font-black text-heal-ink dark:text-white">Privacidade</h2>
      <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-zinc-400">
        Os dados ficam em users/uid e subcolecoes. As regras negam tudo por padrao e permitem acesso apenas ao uid autenticado.
      </p>
      <div className="mt-5 space-y-4">
        <Toggle label="Ocultar e-mail no topo" checked={settings?.hideEmailPreview ?? false} onChange={value => toggle('hideEmailPreview', value)} />
        <Toggle label="Exibir foto de perfil" checked={settings?.showProfilePhoto ?? true} onChange={value => toggle('showProfilePhoto', value)} />
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
