import { useState } from "react";
import { Link, Navigate } from "react-router-dom";

import { useAuth } from "../../app/providers/AuthProvider";
import {
  friendlyAuthError,
  resetPassword,
  signInWithEmail,
  signInWithGoogle,
  signUpWithEmail,
} from "./authService";

const GoogleIcon = () => (
  <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5">
    <path
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      fill="#4285F4"
    />
    <path
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      fill="#34A853"
    />
    <path
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      fill="#FBBC05"
    />
    <path
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      fill="#EA4335"
    />
  </svg>
);

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
    <main className="relative min-h-screen overflow-x-hidden bg-[#f7faff] text-[#101828]">
      <header className="fixed left-0 top-0 z-50 w-full border-b border-gray-200 bg-white/90 text-gray-900 shadow-sm backdrop-blur-2xl">
        <div className="mx-auto flex h-[76px] w-full max-w-[1530px] items-center justify-between px-5 md:px-8">
        <Link to="/" className="flex min-w-0 items-center gap-3">
          <img
            src="/images/logo.png"
            alt="Heal+ Logo"
            className="h-12 w-12 shrink-0"
          />
          <div className="min-w-0 leading-none">
            <h1 className="text-2xl font-black text-[#3b82f6] font-headline">
              Heal+
            </h1>
            <p className="mt-1 hidden text-[10px] font-extrabold uppercase tracking-[0.24em] text-gray-500 sm:block">
              REDI-SUS Module
            </p>
          </div>
        </Link>
        <div className="hidden items-center gap-7 lg:flex">
          <a href="/#projeto" className="text-sm font-extrabold text-gray-600 transition-colors hover:text-[#3b82f6]">O projeto</a>
          <a href="/#plataforma" className="text-sm font-extrabold text-gray-600 transition-colors hover:text-[#3b82f6]">Plataforma</a>
          <a href="/#fluxo" className="text-sm font-extrabold text-gray-600 transition-colors hover:text-[#3b82f6]">Fluxo</a>
          <a href="/#tecnologia" className="text-sm font-extrabold text-gray-600 transition-colors hover:text-[#3b82f6]">Tecnologia</a>
          <a href="/#instituicoes" className="text-sm font-extrabold text-gray-600 transition-colors hover:text-[#3b82f6]">Instituições</a>
        </div>

        <Link to="/" className="hidden rounded-full px-4 py-2 text-sm font-extrabold text-gray-600 transition-colors hover:text-[#3b82f6] sm:inline-flex">
          Voltar
        </Link>
        </div>
      </header>

      <div className="flex min-h-screen flex-col pt-[76px] md:flex-row">
        <section className="landing-deep-blue relative isolate hidden min-h-[calc(100vh-76px)] w-full overflow-hidden px-[1.875rem] py-[3.375rem] text-white md:flex md:w-3/5 md:items-center lg:px-[3.75rem]">
          <div className="absolute inset-0 -z-10 bg-[radial-gradient(rgba(141,176,255,0.16)_1px,transparent_1px)] bg-[length:34px_34px] opacity-25" />
          <div className="pointer-events-none absolute inset-y-0 right-0 z-0 hidden w-[52%] overflow-hidden xl:block">
            <img
              src="/images/Hero imagem.png"
              alt=""
              aria-hidden="true"
              className="absolute bottom-0 right-[-38%] w-[170%] max-w-none object-contain object-bottom drop-shadow-[0_30px_58px_rgba(0,0,0,0.22)]"
            />
          </div>

          <div className="relative z-10 max-w-[520px]">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[#73a8ff]/25 bg-[#3b82f6]/12 px-3 py-1.5 text-[11px] font-black uppercase tracking-[0.18em] text-[#cfe3ff]">
              <span className="material-symbols-outlined text-sm">verified</span>
              <span>
                Plataforma Clínica Segura
              </span>
            </div>
            <h1 className="font-headline text-3xl font-black leading-[1.02] tracking-[-0.04em] md:text-[3rem]">
              Monitoramento inteligente para <span className="text-[#9fc8ff]">equipes clínicas</span>
            </h1>
            <p className="mt-4 max-w-xl text-base leading-7 text-white/78">
              Acesse avaliações, acompanhe evolução de lesões e centralize dados assistenciais com mais clareza e foco.
            </p>

            <div className="mt-7 rounded-[1.25rem] border border-white/10 bg-[#21106f]/70 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] backdrop-blur-xl">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="font-headline text-2xl font-black text-[#73a8ff]">98.4%</div>
                  <div className="mt-1 text-[11px] font-bold uppercase tracking-[0.18em] text-white/70">
                    Rastreamento de Casos
                  </div>
                </div>
                <div>
                  <div className="font-headline text-2xl font-black text-[#73a8ff]">24/7</div>
                  <div className="mt-1 text-[11px] font-bold uppercase tracking-[0.18em] text-white/70">
                    Operação Contínua
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="relative z-30 flex min-h-[calc(100vh-76px)] w-full flex-col justify-center bg-[#f7faff] p-6 md:w-2/5 md:border-l md:border-[#dbeafe] md:p-[2.625rem]">
          <Link
            to="/"
            className="mb-6 inline-flex w-fit items-center gap-2 rounded-full border border-[#dbeafe] bg-white px-3 py-2 text-xs font-bold text-[#667085] shadow-[0_18px_45px_rgba(59,130,246,0.06)] transition-all hover:border-[#93c5fd] hover:text-[#2563eb]"
          >
            <span className="material-symbols-outlined text-base">arrow_back</span>
            Voltar para página principal
          </Link>

          <div className="mb-4">
            <p className="text-[11px] font-black uppercase tracking-[0.18em] text-[#3b82f6]">Acesso Profissional</p>
          </div>

          <div className="w-full max-w-md">
            <div className="mb-6">
              <h2 className="font-headline text-3xl font-black tracking-[-0.04em] text-[#061235] md:text-[2rem]">
                {title}
              </h2>
              <p className="mt-2 max-w-md text-sm leading-relaxed text-[#667085]">
                Acesse os dados clínicos e gerencie o histórico de modo seguro.
              </p>
            </div>

            <div className="rounded-[1.5rem] border border-[#dbeafe] bg-white p-6 shadow-[0_24px_70px_rgba(59,130,246,0.12)] md:p-[1.875rem]">
              <form className="space-y-4" onSubmit={handleSubmit}>
                <label className="block space-y-2">
                  <span className="ml-1 text-[11px] font-bold uppercase tracking-[0.18em] text-[#667085]">
                    E-mail profissional
                  </span>
                  <div className="group relative">
                    <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-base text-[#93a4bc] transition-colors group-hover:text-[#3b82f6]">
                      mail
                    </span>
                    <input
                      type="email"
                      className="h-12 w-full rounded-xl border border-[#dbeafe] bg-[#f7faff] pl-12 pr-4 text-sm text-[#101828] outline-none transition-all placeholder:text-[#93a4bc] hover:border-[#bfdbfe] focus:border-[#3b82f6] focus:ring-2 focus:ring-[#3b82f6]/25"
                      placeholder="seu.nome@hospital.org"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      required
                    />
                  </div>
                </label>

                <label className="block space-y-2">
                  <span className="ml-1 flex items-center justify-between">
                    <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#667085]">
                      Senha
                    </span>
                    {mode === "login" ? (
                      <button
                        type="button"
                        onClick={handleResetPassword}
                        className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#2563eb] transition-colors hover:text-[#3b82f6] disabled:opacity-50"
                        disabled={loading}
                      >
                        Esqueceu?
                      </button>
                    ) : null}
                  </span>
                  <div className="group relative">
                    <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-base text-[#93a4bc] transition-colors group-hover:text-[#3b82f6]">
                      lock
                    </span>
                    <input
                      type="password"
                      className="h-12 w-full rounded-xl border border-[#dbeafe] bg-[#f7faff] pl-12 pr-4 text-sm text-[#101828] outline-none transition-all placeholder:text-[#93a4bc] hover:border-[#bfdbfe] focus:border-[#3b82f6] focus:ring-2 focus:ring-[#3b82f6]/25"
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
                  className="landing-blue-button mt-1 flex h-12 w-full items-center justify-center gap-2 rounded-xl text-sm font-black text-white transition-all hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={loading}
                >
                  {loading ? "Processando..." : actionLabel}
                  {!loading ? (
                    <span className="material-symbols-outlined text-base">
                      {mode === "login" ? "login" : "person_add"}
                    </span>
                  ) : null}
                </button>

                <div className="flex items-center gap-4 py-3">
                  <div className="h-px flex-1 bg-[#dbeafe]" />
                  <span className="shrink-0 text-[10px] font-bold uppercase tracking-[0.16em] text-[#667085]">
                    Ou continuar com
                  </span>
                  <div className="h-px flex-1 bg-[#dbeafe]" />
                </div>

                <button
                  type="button"
                  className="group flex h-11 w-full items-center justify-center gap-3 rounded-xl border border-[#dbeafe] bg-[#f7faff] text-sm font-bold text-[#061235] transition-all hover:border-[#93c5fd] hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={googleLoading || loading}
                  onClick={handleGoogleSignIn}
                >
                  {!googleLoading ? <GoogleIcon /> : null}
                  {googleLoading ? "Conectando..." : "Google"}
                </button>
              </form>
            </div>

            <div className="mt-6 flex items-center justify-center gap-2 text-sm">
              <span className="text-[#667085]">
                {mode === "login" ? "Novo na plataforma?" : "Já possui uma conta?"}
              </span>
              <button
                type="button"
                className="font-bold text-[#2563eb] transition-colors hover:text-[#3b82f6]"
                onClick={() => setMode((current) => (current === "login" ? "register" : "login"))}
              >
                {mode === "login" ? "Crie sua conta" : "Entre agora"}
              </button>
            </div>
          </div>
        </section>
      </div>

      <footer className="absolute bottom-0 left-0 z-20 hidden w-full items-center justify-start px-10 py-5 md:flex">
        <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-white/55">
          © 2026 Redisus Heal+.
        </div>
      </footer>
    </main>
  );
}
