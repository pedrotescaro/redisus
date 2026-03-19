"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { signInWithEmail, signInWithGoogle, signUpWithEmail } from "@/services/firebase/auth-service";
import { Mail, Lock, LogIn, UserPlus } from "lucide-react";

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

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
        await signUpWithEmail(email, password);
      }

      router.replace("/dashboard");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Falha ao autenticar.";
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
      const message = err instanceof Error ? err.message : "Falha ao autenticar com Google.";
      setError(message);
    } finally {
      setGoogleLoading(false);
    }
  };

  return (
    <div className="w-full max-w-sm mx-auto flex flex-col justify-center h-full">
      <div className="mb-8">
        <h2 className="text-3xl font-bold tracking-tight text-slate-900">{title}</h2>
        <p className="mt-2 text-sm text-slate-500">
          Acesse os dados clínicos e gerencie o histórico de modo seguro.
        </p>
      </div>

      <form className="space-y-5" onSubmit={handleSubmit}>
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-slate-700" htmlFor="email">
            E-mail profissional
          </label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
            <Input
              id="email"
              name="email"
              type="email"
              className="pl-11 h-12"
              placeholder="seu.nome@hospital.org"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium text-slate-700" htmlFor="password">
            Senha
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
            <Input
              id="password"
              name="password"
              type="password"
              className="pl-11 h-12"
              placeholder="••••••••"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600 font-medium pb-2">
            {error}
          </div>
        )}

        <Button type="submit" className="w-full font-medium h-12 text-base transition-all mt-4" disabled={loading}>
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="w-5 h-5 rounded-full border-2 border-white/30 border-t-white animate-spin"></span>
              Processando...
            </span>
          ) : (
            <span className="flex items-center gap-2">
              {mode === "login" ? <LogIn className="h-5 w-5" /> : <UserPlus className="h-5 w-5" />}
              {actionLabel}
            </span>
          )}
        </Button>

        <div className="relative py-4">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t border-slate-200" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-white px-3 text-slate-500 font-medium">Ou continuar com</span>
          </div>
        </div>

        <Button
          type="button"
          variant="outline"
          className="w-full font-medium h-12 text-base text-slate-700 hover:bg-slate-50 hover:text-slate-900 border-slate-200 shadow-sm"
          disabled={googleLoading || loading}
          onClick={handleGoogleSignIn}
        >
          {googleLoading ? (
            <span className="flex items-center gap-2">
              <span className="w-5 h-5 rounded-full border-2 border-brand-500/30 border-t-brand-600 animate-spin"></span>
              Conectando...
            </span>
          ) : (
            <span className="flex items-center justify-center gap-3">
              <svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
              Google
            </span>
          )}
        </Button>
      </form>

      <div className="mt-8 pt-6 flex items-center justify-center gap-2 text-sm">
        <span className="text-slate-500">
          {mode === "login" ? "Novo na plataforma?" : "Já possui uma conta?"}
        </span>
        <button
          type="button"
          className="font-medium text-brand-600 hover:text-brand-800 transition-colors"
          onClick={() => setMode((current) => (current === "login" ? "register" : "login"))}
        >
          {mode === "login" ? "Crie sua conta" : "Entre agora"}
        </button>
      </div>
    </div>
  );
}
