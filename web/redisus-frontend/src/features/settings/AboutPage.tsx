import { APP_VERSION } from '../../lib/constants';
import { Card } from '../../components/ui/Card';

export function AboutPage() {
  return (
    <Card className="mx-auto max-w-3xl border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e] p-5">
      <h2 className="text-lg font-black text-heal-ink dark:text-white">Sobre o Heal+</h2>
      <p className="mt-3 text-xs leading-5 text-slate-600 dark:text-zinc-400">
        Versão web acadêmica do Heal+, reconstruída em React, TypeScript, Vite e Firebase para demonstrar testes de autenticação,
        regras, persistência, upload, ROI e relatórios.
      </p>
      <p className="mt-4 text-xs font-semibold text-slate-500 dark:text-zinc-500">Versão {APP_VERSION}</p>
    </Card>
  );
}
