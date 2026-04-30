import { useState } from "react";
import { Link, Navigate } from "react-router-dom";

import { useAuth } from "../../app/providers/AuthProvider";
import { ThemeToggle } from "../../components/theme-toggle";
import {
  friendlyAuthError,
  resetPassword,
  signInWithEmail,
  signInWithGoogle,
  signUpWithEmail,
} from "./authService";

export function LoginPage() {
  const { user } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resetSent, setResetSent] = useState(false);

  if (user) return <Navigate to="/dashboard" replace />;

  const title = mode === "login" ? "Entrar no Heal+" : "Cadastrar profissional";
  const actionLabel = mode === "login" ? "Entrar" : "Criar conta";

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (mode === "login") {
        await signInWithEmail(email, password);
      } else {
        const name = email.split("@")[0] || "Profissional";
        await signUpWithEmail(name, email, password);
      }
    } catch (err) {
      setError(friendlyAuthError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setGoogleLoading(true);
    setError(null);

    try {
      await signInWithGoogle();
    } catch (err) {
      setError(friendlyAuthError(err));
    } finally {
      setGoogleLoading(false);
    }
  };

  const handleResetPassword = async () => {
    setError(null);
    setResetSent(false);

    if (!email) {
      setError("Por favor, preencha o campo de e-mail antes para recuperar a senha.");
      return;
    }

    setLoading(true);
    try {
      await resetPassword(email);
      setResetSent(true);
    } catch (err) {
      setError(friendlyAuthError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-surface text-on-surface">
      <header className="absolute left-0 top-0 z-30 flex w-full items-center justify-between px-6 py-6 md:px-10">
        <Link to="/" className="group flex items-center gap-2">
          <img
            src="/images/logo.png"
            alt="Heal+ Logo"
            className="h-14 w-14 transition-transform group-hover:scale-105"
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
          <div className="absolute inset-0 bg-gradient-to-r from-surface via-surface-container-high/90 to-surface-container/80" />
          <div className="absolute left-10 top-36 h-40 w-40 rounded-full bg-primary/10 blur-[96px]" />
          <div className="absolute bottom-24 right-14 h-56 w-56 rounded-full bg-primary-container/15 blur-[120px]" />

          <div className="relative z-10 max-w-2xl">
            <div className="mb-8 inline-flex items-center gap-2 rounded-full bg-primary-container/10 px-3 py-1.5 ghost-border">
              <span className="material-symbols-outlined text-sm text-primary">verified</span>
              <span className="text-[10px] font-bold uppercase tracking-[0.22em] text-primary">
                Plataforma Clínica Segura
              </span>
            </div>
            <h1 className="font-headline text-4xl font-extrabold leading-[1.05] tracking-tight text-on-surface md:text-5xl">
              Monitoramento inteligente para <span className="text-primary">equipes clínicas</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-on-surface-variant">
              Acesse avaliações, acompanhe evolução de lesões e centralize dados assistenciais com mais clareza e foco.
            </p>

            <div className="mt-12 rounded-3xl bg-surface-container-high/80 p-6 shadow-ambient backdrop-blur-md ghost-border">
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <div className="font-headline text-2xl font-bold text-on-surface md:text-3xl">98.4%</div>
                  <div className="mt-1 text-xs uppercase tracking-[0.18em] text-on-surface-variant">
                    Rastreamento de Casos
                  </div>
                </div>
                <div>
                  <div className="font-headline text-2xl font-bold text-on-surface md:text-3xl">24/7</div>
                  <div className="mt-1 text-xs uppercase tracking-[0.18em] text-on-surface-variant">
                    Operação Contínua
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="relative z-30 flex min-h-screen w-full flex-col justify-center bg-surface-container-low p-8 shadow-ambient md:w-2/5 md:border-l md:border-black/[0.05] md:p-14 dark:md:border-white/[0.05]">
          <Link
            to="/"
            className="mb-8 inline-flex w-fit items-center gap-2 rounded-xl border border-outline-variant/15 bg-surface-container-low/70 px-4 py-2.5 text-sm font-semibold text-on-surface-variant shadow-ambient transition-all hover:border-primary/30 hover:bg-surface-container hover:text-on-surface"
          >
            <span className="material-symbols-outlined text-base">arrow_back</span>
            Voltar para página principal
          </Link>

          <div className="mb-6">
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-primary/80">Acesso Profissional</p>
          </div>

          <div className="w-full max-w-md">
            <div className="mb-8">
              <h2 className="font-headline text-3xl font-extrabold tracking-tight text-on-surface md:text-4xl">
                {title}
              </h2>
              <p className="mt-2 max-w-md text-sm leading-relaxed text-on-surface-variant">
                Acesse os dados clínicos e gerencie o histórico de modo seguro.
              </p>
            </div>

            <div className="rounded-3xl bg-surface-container-highest/95 p-8 shadow-ambient backdrop-blur-md ghost-border md:p-10">
              <form className="space-y-5" onSubmit={handleSubmit}>
                <label className="block space-y-2">
                  <span className="ml-1 text-[11px] font-bold uppercase tracking-[0.18em] text-on-surface-variant">
                    E-mail profissional
                  </span>
                  <div className="group relative">
                    <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-base text-outline transition-colors group-hover:text-primary">
                      mail
                    </span>
                    <input
                      type="email"
                      className="h-16 w-full rounded-xl border border-outline-variant/20 bg-surface-container-low pl-14 pr-4 text-sm text-on-surface outline-none transition-all placeholder:text-outline/50 hover:border-outline-variant/40 hover:bg-surface-container focus:border-primary focus:ring-2 focus:ring-primary/25"
                      placeholder="seu.nome@hospital.org"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      required
                    />
                  </div>
                </label>

                <label className="block space-y-2">
                  <span className="ml-1 flex items-center justify-between">
                    <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-on-surface-variant">
                      Senha
                    </span>
                    {mode === "login" ? (
                      <button
                        type="button"
                        onClick={handleResetPassword}
                        className="text-[10px] font-bold uppercase tracking-[0.16em] text-primary transition-colors hover:text-primary/80 disabled:opacity-50"
                        disabled={loading}
                      >
                        Esqueceu?
                      </button>
                    ) : null}
                  </span>
                  <div className="group relative">
                    <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-base text-outline transition-colors group-hover:text-primary">
                      lock
                    </span>
                    <input
                      type="password"
                      className="h-16 w-full rounded-xl border border-outline-variant/20 bg-surface-container-low pl-14 pr-4 text-sm text-on-surface outline-none transition-all placeholder:text-outline/50 hover:border-outline-variant/40 hover:bg-surface-container focus:border-primary focus:ring-2 focus:ring-primary/25"
                      placeholder="••••••••"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      required
                    />
                  </div>
                </label>

                {error ? (
                  <div className="flex items-center gap-2 rounded-xl border border-error/30 bg-error-container/20 p-3 text-sm font-medium text-error">
                    <span className="material-symbols-outlined text-sm">error</span>
                    {error}
                  </div>
                ) : null}

                {resetSent ? (
                  <div className="flex items-center gap-2 rounded-xl border border-green-500/30 bg-green-500/10 p-3 text-sm font-medium text-green-700 dark:text-green-400">
                    <span className="material-symbols-outlined text-sm">check_circle</span>
                    E-mail de recuperação enviado!
                  </div>
                ) : null}

                <button
                  type="submit"
                  className="mt-2 flex h-16 w-full items-center justify-center gap-2 rounded-xl bg-primary-gradient text-base font-bold text-on-primary-container shadow-[0_12px_32px_rgba(33,150,243,0.32)] transition-all hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={loading}
                >
                  {loading ? "Processando..." : actionLabel}
                  {!loading ? (
                    <span className="material-symbols-outlined text-base">
                      {mode === "login" ? "login" : "person_add"}
                    </span>
                  ) : null}
                </button>

                <div className="flex items-center gap-4 py-5">
                  <div className="h-px flex-1 bg-outline-variant/30" />
                  <span className="shrink-0 text-[10px] font-bold uppercase tracking-[0.16em] text-on-surface-variant">
                    Ou continuar com
                  </span>
                  <div className="h-px flex-1 bg-outline-variant/30" />
                </div>

                <button
                  type="button"
                  className="group flex h-14 w-full items-center justify-center gap-3 rounded-xl border border-outline-variant/20 bg-surface-container-low text-base font-semibold transition-all hover:border-outline-variant/40 hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={googleLoading || loading}
                  onClick={handleGoogleSignIn}
                >
                  {googleLoading ? "Conectando..." : "Google"}
                </button>
              </form>
            </div>

            <div className="mt-8 flex items-center justify-center gap-2 text-sm">
              <span className="text-on-surface-variant">
                {mode === "login" ? "Novo na plataforma?" : "Já possui uma conta?"}
              </span>
              <button
                type="button"
                className="font-semibold text-primary transition-colors hover:text-primary/80"
                onClick={() => setMode((current) => (current === "login" ? "register" : "login"))}
              >
                {mode === "login" ? "Crie sua conta" : "Entre agora"}
              </button>
            </div>
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
