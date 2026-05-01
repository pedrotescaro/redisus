import { BarChart3, Camera, ClipboardCheck, FileText, ShieldCheck, Users } from 'lucide-react';
import type { ReactNode } from 'react';

import healBannerUrl from '../../assets/brand/healplus-login-banner.jpg';
import healLogoUrl from '../../assets/brand/logo.png';

interface AuthLayoutProps {
  children: ReactNode;
  title: string;
  subtitle: string;
}

const features = [
  { icon: Users, label: 'Cadastro assistencial', value: 'Pacientes ativos e arquivados' },
  { icon: ClipboardCheck, label: 'Avaliação clínica', value: 'TIMERS, imagem e demarcação' },
  { icon: BarChart3, label: 'Evolução visível', value: 'Comparativos e indicadores' },
  { icon: FileText, label: 'Relatórios', value: 'Documentos para revisão' },
  { icon: ShieldCheck, label: 'Acesso protegido', value: 'Conta profissional autenticada' },
  { icon: Camera, label: 'Registro fotográfico', value: 'Imagem e ROI no prontuário' }
];

export function AuthLayout({ children, title, subtitle }: AuthLayoutProps) {
  return (
    <main className="min-h-screen bg-[#03142a] px-4 py-5 text-white sm:px-6 lg:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-2.5rem)] w-full max-w-7xl flex-col gap-5">
        <BrandBanner />

        <section className="grid flex-1 overflow-hidden rounded-[1.5rem] border border-sky-300/20 bg-[#061a34] shadow-soft lg:grid-cols-[440px_1fr]">
          <div className="bg-white p-6 text-slate-950 sm:p-8 lg:p-9">
            <div className="mb-8">
              <p className="mb-4 text-xs font-black uppercase tracking-[0.18em] text-[#007bff]">Portal de acesso seguro</p>
              <div className="flex items-center gap-3">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-sky-50 shadow-sm ring-1 ring-sky-100">
                  <img src={healLogoUrl} alt="Heal+" className="h-12 w-12 object-contain" />
                </div>
                <div>
                  <p className="text-3xl font-black tracking-tight text-[#0088ff]">Heal+</p>
                  <p className="text-sm font-bold text-slate-500">Plataforma clínica web</p>
                </div>
              </div>
            </div>

            <h1 className="text-3xl font-black tracking-tight text-slate-950">{title}</h1>
            <p className="mt-2 text-sm leading-6 text-slate-600">{subtitle}</p>
            <div className="mt-8 [&_input]:!border-slate-200 [&_input]:!bg-white [&_input]:!text-slate-950 [&_label]:!text-slate-950">
              {children}
            </div>
          </div>

          <aside className="hidden p-8 lg:block">
            <div className="flex h-full flex-col justify-between gap-8">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.18em] text-[#00a6ff]">Heal+ Web</p>
                <h2 className="mt-4 max-w-2xl text-5xl font-black leading-tight tracking-tight text-white">
                  Cuidado inteligente. Evolução visível.
                </h2>
                <p className="mt-5 max-w-xl text-base leading-7 text-sky-100/80">
                  Ambiente profissional com identidade institucional, acesso seguro e fluxo clínico para acompanhamento de feridas.
                </p>
              </div>

              <div className="grid gap-3 xl:grid-cols-2">
                {features.map(feature => (
                  <div key={feature.label} className="rounded-2xl border border-sky-200/15 bg-white/[0.06] p-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#0088ff]/15 text-[#36b8ff]">
                        <feature.icon className="h-5 w-5" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-black text-white">{feature.label}</p>
                        <p className="truncate text-xs font-semibold text-sky-100/70">{feature.value}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="rounded-2xl border border-[#0088ff]/25 bg-[#0088ff]/10 p-5">
                <p className="text-sm font-black text-white">Regra clínica preservada</p>
                <p className="mt-1 text-sm leading-6 text-sky-100/80">
                  Pacientes ficam salvos e podem ser arquivados. Exclusão direta fica restrita aos agendamentos.
                </p>
              </div>
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}

function BrandBanner() {
  return (
    <header className="overflow-hidden rounded-[1.25rem] border border-sky-300/20 bg-[#020f22] shadow-soft">
      <img
        src={healBannerUrl}
        alt="Heal+ com RNP, Fatec Ferraz de Vasconcelos e Centro Paula Souza"
        className="h-28 w-full object-cover object-center sm:h-36 lg:h-40"
      />
    </header>
  );
}
