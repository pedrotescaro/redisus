import { zodResolver } from '@hookform/resolvers/zod';
import { Mail, Lock, User as UserIcon } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, Navigate, useNavigate } from 'react-router-dom';

import { useAuth } from '../../app/providers/AuthProvider';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { AuthLayout } from '../../components/layout/AuthLayout';
import { SocialLoginButton } from '../../components/layout/SocialLoginButton';
import {
  friendlyAuthError,
  registerWithEmail,
  signInWithGoogle,
  signInWithMicrosoft,
  signInWithApple
} from './authService';
import { registerSchema, type RegisterFormValues } from './authSchema';

const GoogleIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
  </svg>
);

const MicrosoftIcon = () => (
  <svg viewBox="0 0 21 21" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M10 0H0V10H10V0Z" fill="#F25022"/>
    <path d="M21 0H11V10H21V0Z" fill="#7FBA00"/>
    <path d="M10 11H0V21H10V11Z" fill="#00A4EF"/>
    <path d="M21 11H11V21H21V11Z" fill="#FFB900"/>
  </svg>
);

const AppleIcon = () => (
  <svg viewBox="0 0 384 512" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
    <path d="M318.7 268.7c-.2-36.7 16.4-64.4 50-84.8-18.8-26.9-47.2-41.7-84.7-44.6-35.5-2.8-74.3 20.7-88.5 20.7-15 0-49.4-19.7-76.4-19.7C63.3 141.2 4 184.8 4 273.5q0 39.3 14.4 81.2c12.8 36.7 59 126.7 107.2 125.2 25.2-.6 43-17.9 75.8-17.9 31.8 0 48.3 17.9 76.4 17.9 48.6-.7 90.4-82.5 102.6-119.3-65.2-30.7-61.7-90-61.7-91.9zm-56.6-164.2c27.3-32.4 24.8-61.9 24-72.5-24.1 1.4-52 16.4-67.9 34.9-17.5 19.8-27.8 44.3-25.6 71.9 26.1 2 49.9-11.4 69.5-34.3z"/>
  </svg>
);

export function RegisterPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [socialLoading, setSocialLoading] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting }
  } = useForm<RegisterFormValues>({ resolver: zodResolver(registerSchema), defaultValues: { acceptedTerms: false } });

  if (user) return <Navigate to="/dashboard" replace />;

  const onSubmit = async (values: RegisterFormValues) => {
    setError('');
    try {
      await registerWithEmail(values);
      navigate('/onboarding');
    } catch (err) {
      setError(friendlyAuthError(err));
    }
  };

  const handleSocial = async (provider: 'google' | 'microsoft' | 'apple') => {
    setError('');
    setSocialLoading(provider);
    try {
      if (provider === 'google') await signInWithGoogle();
      else if (provider === 'microsoft') await signInWithMicrosoft();
      else await signInWithApple();
      navigate('/dashboard');
    } catch (err) {
      setError(friendlyAuthError(err));
    } finally {
      setSocialLoading(null);
    }
  };

  const busy = isSubmitting || !!socialLoading;

  return (
    <AuthLayout title="Criar conta" subtitle="Junte-se ao Heal+ e organize seu cuidado clinico.">
      <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
        <Input
          label="Nome profissional"
          icon={<UserIcon className="h-4 w-4" />}
          error={errors.displayName?.message}
          {...register('displayName')}
          disabled={busy}
        />

        <Input
          label="E-mail profissional"
          type="email"
          autoComplete="email"
          icon={<Mail className="h-4 w-4" />}
          error={errors.email?.message}
          {...register('email')}
          disabled={busy}
        />

        <Input
          label="Senha"
          type="password"
          autoComplete="new-password"
          icon={<Lock className="h-4 w-4" />}
          error={errors.password?.message}
          {...register('password')}
          disabled={busy}
        />

        <Input
          label="Confirmar senha"
          type="password"
          autoComplete="new-password"
          icon={<Lock className="h-4 w-4" />}
          error={errors.confirmPassword?.message}
          {...register('confirmPassword')}
          disabled={busy}
        />

        <div className="flex items-start gap-2.5 text-sm text-heal-muted pt-1">
          <input
            type="checkbox"
            id="terms"
            className="mt-0.5 h-4 w-4 rounded border-heal-line text-heal-blue focus:ring-heal-blue"
            disabled={busy}
            {...register('acceptedTerms')}
          />
          <label htmlFor="terms" className="leading-relaxed">
            Eu concordo com os Termos de Uso e a Politica de Privacidade do Heal+.
          </label>
        </div>

        {errors.acceptedTerms?.message ? <p className="text-xs font-bold text-heal-danger">{errors.acceptedTerms.message}</p> : null}

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 dark:border-red-900/30 dark:bg-red-950/30">
            <p className="text-sm font-medium text-red-800 dark:text-red-300">{error}</p>
          </div>
        )}

        <Button type="submit" className="w-full" size="lg" isLoading={isSubmitting} disabled={busy}>
          Cadastrar
        </Button>
      </form>

      {/* Divider */}
      <div className="mt-8">
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-heal-line dark:border-zinc-700" />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="bg-white px-3 font-medium text-heal-muted dark:bg-zinc-900">ou cadastre-se com</span>
          </div>
        </div>

        <div className="mt-6 space-y-3">
          <SocialLoginButton provider="google" disabled={busy} isLoading={socialLoading === 'google'} onClick={() => handleSocial('google')} icon={<GoogleIcon />} />
          <SocialLoginButton provider="microsoft" disabled={busy} isLoading={socialLoading === 'microsoft'} onClick={() => handleSocial('microsoft')} icon={<MicrosoftIcon />} />
          <SocialLoginButton provider="apple" disabled={busy} isLoading={socialLoading === 'apple'} onClick={() => handleSocial('apple')} icon={<AppleIcon />} />
        </div>
      </div>

      <p className="mt-8 text-center text-sm text-heal-muted">
        Ja tem uma conta?{' '}
        <Link to="/login" className="font-semibold text-heal-blue hover:text-heal-blueDark transition-colors">
          Fazer login
        </Link>
      </p>
    </AuthLayout>
  );
}
