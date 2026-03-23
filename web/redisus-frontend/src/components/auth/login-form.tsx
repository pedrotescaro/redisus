"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  signInWithEmail,
  signInWithGoogle,
  signUpWithEmail,
} from "@/services/firebase/auth-service";

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const title =
    mode === "login" ? "Entrar no Heal+" : "Cadastrar profissional";
  const actionLabel = mode === "login" ? "Entrar" : "Criar conta";

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (mode === "login") {
        await signInWithEmail(email, password);
      } else {
        await signUpWithEmail(email, password);
      }

      router.replace("/dashboard");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Falha ao autenticar.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setGoogleLoading(true);
    setError(null);

    try {
      await signInWithGoogle();
      router.replace("/dashboard");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Falha ao autenticar com Google.";
      setError(message);
    } finally {
      setGoogleLoading(false);
    }
  };

  return (
    <div className="w-full">
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
          <div className="space-y-2">
            <label
              className="ml-1 text-[11px] font-bold uppercase tracking-[0.18em] text-on-surface-variant"
              htmlFor="email"
            >
              E-mail profissional
            </label>
            <div className="relative group">
              <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-base text-outline transition-colors group-hover:text-primary">
                mail
              </span>
                <Input
                id="email"
                name="email"
                type="email"
                className="h-16 rounded-xl border border-outline-variant/20 bg-surface-container-low pl-14 text-sm placeholder:text-outline/50 focus:ring-primary/25 hover:border-outline-variant/40 hover:bg-surface-container dark:hover:border-outline-variant/30 transition-all cursor-text peer"
                placeholder="seu.nome@hospital.org"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="ml-1 flex items-center justify-between">
              <label
                className="text-[11px] font-bold uppercase tracking-[0.18em] text-on-surface-variant"
                htmlFor="password"
              >
                Senha
              </label>
              {mode === "login" && (
                <a
                  href="#"
                  className="text-[10px] font-bold uppercase tracking-[0.16em] text-primary transition-colors hover:text-primary/80"
                >
                  Esqueceu?
                </a>
              )}
            </div>
            <div className="relative group">
              <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-base text-outline transition-colors group-hover:text-primary">
                lock
              </span>
              <Input
                id="password"
                name="password"
                type="password"
                className="h-16 rounded-xl border border-outline-variant/20 bg-surface-container-low pl-14 text-sm placeholder:text-outline/50 focus:ring-primary/25 hover:border-outline-variant/40 hover:bg-surface-container dark:hover:border-outline-variant/30 transition-all cursor-text peer"
                placeholder="••••••••"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-xl border border-error/30 bg-error-container/20 p-3 text-sm font-medium text-error">
              <span className="material-symbols-outlined text-sm">error</span>
              {error}
            </div>
          )}

            <Button
            type="submit"
            className="mt-2 h-16 w-full rounded-xl bg-primary-gradient text-base font-bold text-on-primary-container shadow-[0_12px_32px_rgba(33,150,243,0.32)] transition-all hover:brightness-110"
            disabled={loading}
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-white"></span>
                Processando...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <span>{actionLabel}</span>
                <span className="material-symbols-outlined text-base">
                  {mode === "login" ? "login" : "person_add"}
                </span>
              </span>
            )}
          </Button>

          <div className="flex items-center gap-4 py-5">
            <div className="h-px flex-1 bg-outline-variant/30 border-0"></div>
            <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-on-surface-variant flex-shrink-0">
              Ou continuar com
            </span>
            <div className="h-px flex-1 bg-outline-variant/30 border-0"></div>
          </div>

          <Button
            type="button"
            variant="outline"
            className="group h-14 w-full rounded-xl border border-outline-variant/20 bg-surface-container-low text-base font-semibold hover:border-outline-variant/40 hover:bg-surface-container dark:hover:border-outline-variant/30 transition-all"
            disabled={googleLoading || loading}
            onClick={handleGoogleSignIn}
          >
            {googleLoading ? (
              <span className="flex items-center gap-2">
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-primary/30 border-t-primary"></span>
                Conectando...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-3">
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
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
                Google
              </span>
            )}
          </Button>
        </form>
      </div>

      <div className="mt-8 flex items-center justify-center gap-2 text-sm">
        <span className="text-on-surface-variant">
          {mode === "login" ? "Novo na plataforma?" : "Já possui uma conta?"}
        </span>
        <button
          type="button"
          className="font-semibold text-primary transition-colors hover:text-primary/80"
          onClick={() =>
            setMode((current) => (current === "login" ? "register" : "login"))
          }
        >
          {mode === "login" ? "Crie sua conta" : "Entre agora"}
        </button>
      </div>

      <p className="mt-3 text-center text-xs text-outline">
        Não tem uma conta?{" "}
        <a href="#" className="font-semibold text-primary hover:underline">
          Falar com o administrador
        </a>
      </p>
    </div>
  );
}
