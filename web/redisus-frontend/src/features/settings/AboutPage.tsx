import { APP_VERSION } from '../../lib/constants';
import { Card } from '../../components/ui/Card';

export function AboutPage() {
  return (
    <Card className="mx-auto max-w-3xl">
      <h2 className="text-2xl font-black text-heal-ink dark:text-white">Sobre o Heal+</h2>
      <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-zinc-300">
        Versao web academica do Heal+, reconstruida em React, TypeScript, Vite e Firebase para demonstrar testes de autenticacao,
        regras, persistencia, upload, ROI e relatorios.
      </p>
      <p className="mt-4 text-sm font-semibold text-slate-500 dark:text-zinc-400">Versao {APP_VERSION}</p>
    </Card>
  );
}
