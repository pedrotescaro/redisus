import { CheckCircle2, ShieldCheck } from 'lucide-react';
import type { ReactNode } from 'react';

import { BrandLogo } from '../brand/BrandLogo';

const highlights = [
  'Gestão de pacientes',
  'Avaliação estruturada',
  'Comparativo fotográfico',
  'Relatórios em PDF',
  'Segurança com Firebase'
];

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="min-h-screen bg-heal-canvas px-4 py-8 text-heal-ink dark:bg-zinc-950">
      <div className="mx-auto grid min-h-[calc(100vh-4rem)] w-full max-w-6xl items-center gap-8 lg:grid-cols-[1fr_0.9fr]">
        <section className="order-2 hidden overflow-hidden rounded-[1.75rem] border border-white/80 bg-white/80 p-8 shadow-soft backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/80 lg:block">
          <BrandLogo />
          <div className="mt-12 max-w-xl">
            <p className="text-sm font-bold uppercase tracking-[0.2em] text-heal-teal">Central clínica web</p>
            <h2 className="mt-4 text-4xl font-black leading-tight text-heal-ink dark:text-white">
              Cuidado inteligente. Evolução visível.
            </h2>
            <p className="mt-4 text-base leading-7 text-heal-muted dark:text-zinc-400">
              Organize pacientes, avaliações, imagens, agenda clínica e relatórios em uma experiência segura, pensada
              para acompanhamento profissional de feridas.
            </p>
          </div>

          <div className="mt-10 grid gap-3">
            {highlights.map(item => (
              <div key={item} className="flex items-center gap-3 rounded-2xl border border-heal-line bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950">
                <CheckCircle2 className="h-5 w-5 text-heal-teal" />
                <span className="text-sm font-bold text-heal-ink dark:text-white">{item}</span>
              </div>
            ))}
          </div>

          <div className="mt-8 rounded-2xl bg-heal-softBlue p-5 dark:bg-blue-950/30">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-5 w-5 text-heal-blue" />
              <div>
                <p className="text-sm font-black text-heal-ink dark:text-white">Dados reais, separados por usuário</p>
                <p className="mt-1 text-sm leading-6 text-heal-muted dark:text-zinc-400">
                  Auth, Firestore, Storage e Rules trabalham juntos para manter cada profissional no próprio espaço.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="order-1 mx-auto w-full max-w-md lg:order-1">{children}</section>
      </div>
    </main>
  );
}
