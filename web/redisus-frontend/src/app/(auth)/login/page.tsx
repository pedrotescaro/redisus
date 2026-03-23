import Image from "next/image";
import Link from "next/link";
import { LoginForm } from "@/components/auth/login-form";
import { ThemeToggle } from "@/components/theme-toggle";

export default function LoginPage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-surface text-on-surface">
      <header className="absolute left-0 top-0 z-30 flex w-full items-center justify-between px-6 py-6 md:px-10">
        <Link href="/" className="group flex items-center gap-2">
          <Image
            src="/images/logo.png"
            alt="Heal+ Logo"
            width={56}
            height={56}
            className="transition-transform group-hover:scale-105"
          />
          <div className="-ml-1">
            <h1 className="font-headline text-2xl font-extrabold leading-none tracking-tight text-primary">
              Heal+
            </h1>
            <p className="mt-0.5 text-[10px] font-bold uppercase tracking-widest text-on-surface-variant opacity-70">
              REDI-SUS
            </p>
          </div>
        </Link>
        <ThemeToggle />
      </header>

      <div className="flex min-h-screen flex-col md:flex-row">
        <section className="relative hidden min-h-screen w-full overflow-hidden bg-surface px-10 py-24 md:flex md:w-3/5 md:items-center lg:px-20">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,var(--primary)_0.12,transparent_50%),radial-gradient(circle_at_85%_35%,var(--primary)_0.08,transparent_50%)]" />
          <div className="absolute inset-0 bg-gradient-to-r from-surface via-surface-container-high/90 to-surface-container/80" />
          <div className="absolute left-10 top-36 h-40 w-40 rounded-full bg-primary/10 blur-[96px]" />
          <div className="absolute bottom-24 right-14 h-56 w-56 rounded-full bg-primary-container/15 blur-[120px]" />

          <div className="relative z-10 max-w-2xl">
            <div className="mb-8 inline-flex items-center gap-2 rounded-full bg-primary-container/10 px-3 py-1.5 ghost-border">
              <span className="material-symbols-outlined text-sm text-primary">
                verified
              </span>
              <span className="text-[10px] font-bold uppercase tracking-[0.22em] text-primary">
                Plataforma Clínica Segura
              </span>
            </div>
            <h1 className="font-headline text-4xl md:text-5xl font-extrabold leading-[1.05] tracking-tight text-on-surface">
              Monitoramento inteligente para{" "}
              <span className="text-primary">equipes clínicas</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-on-surface-variant">
              Acesse avaliações, acompanhe evolução de lesões e centralize dados
              assistenciais com mais clareza e foco.
            </p>

            <div className="mt-12 rounded-3xl bg-surface-container-high/80 p-6 backdrop-blur-md ghost-border shadow-ambient">
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <div className="font-headline text-2xl md:text-3xl font-bold text-on-surface">
                    98.4%
                  </div>
                  <div className="mt-1 text-xs uppercase tracking-[0.18em] text-on-surface-variant">
                    Rastreamento de Casos
                  </div>
                </div>
                <div>
                  <div className="font-headline text-2xl md:text-3xl font-bold text-on-surface">
                    24/7
                  </div>
                  <div className="mt-1 text-xs uppercase tracking-[0.18em] text-on-surface-variant">
                    Operação Contínua
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="relative z-30 flex min-h-screen w-full flex-col justify-center bg-surface-container-low p-8 md:w-2/5 md:border-l dark:md:border-white/[0.05] md:border-black/[0.05] md:p-14 shadow-ambient">
          <Link
            href="/"
            className="mb-8 inline-flex w-fit items-center gap-2 rounded-xl border border-outline-variant/15 bg-surface-container-low/70 px-4 py-2.5 text-sm font-semibold text-on-surface-variant transition-all hover:border-primary/30 hover:bg-surface-container hover:text-on-surface shadow-ambient"
          >
            <span className="material-symbols-outlined text-base">arrow_back</span>
            Voltar para página principal
          </Link>
          <div className="mb-6">
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-primary/80">
              Acesso Profissional
            </p>
          </div>
          <div className="w-full max-w-md">
            <LoginForm />
          </div>
        </section>
      </div>

      <footer className="absolute bottom-0 left-0 z-20 hidden w-full items-center justify-start px-10 py-5 md:flex">
        <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-outline">
          © 2026 Redisus Heal+.
        </div>
      </footer>
    </main>
  );
}

