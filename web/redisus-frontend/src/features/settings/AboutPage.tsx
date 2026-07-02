import { APP_VERSION } from '../../lib/constants';
import { PageHeader } from '../../components/ui/PageHeader';

export function AboutPage() {
  return (
    <div className="flex flex-col xl:flex-row min-h-screen min-w-0 bg-white dark:bg-[#0c0c0e]">
      {/* Coluna Central */}
      <div className="flex-grow max-w-2xl w-full border-r border-heal-line dark:border-zinc-800/60 min-h-screen flex flex-col min-w-0">
        <PageHeader showBack title="Sobre o Heal+" description={`Versão ${APP_VERSION}`} />

        <div className="p-4 sm:p-6 space-y-4">
          <p className="text-xs leading-relaxed text-slate-600 dark:text-zinc-400 select-none">
            Versão web acadêmica do Heal+, reconstruída em React, TypeScript, Vite, Firebase e Supabase para demonstrar testes de autenticação,
            regras, persistência, upload, ROI e relatórios.
          </p>
          <p className="text-[10px] font-bold text-slate-400 dark:text-zinc-600 uppercase tracking-wider select-none">
            Versão do Aplicativo: {APP_VERSION}
          </p>
        </div>
      </div>
    </div>
  );
}
