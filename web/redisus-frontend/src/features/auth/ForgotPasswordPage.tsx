import { zodResolver } from '@hookform/resolvers/zod';
import { Mail, ArrowLeft, CheckCircle2 } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link } from 'react-router-dom';
import { z } from 'zod';

import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { AuthLayout } from '../../components/layout/AuthLayout';
import { friendlyAuthError, resetPassword } from './authService';

const schema = z.object({
  email: z.string().email('Informe um e-mail valido.'),
});

type FormValues = z.infer<typeof schema>;

export function ForgotPasswordPage() {
  const [error, setError] = useState('');
  const [sent, setSent] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: FormValues) => {
    setError('');
    try {
      await resetPassword(values.email);
      setSent(true);
    } catch (err) {
      setError(friendlyAuthError(err));
    }
  };

  return (
    <AuthLayout title="Recuperar senha" subtitle="Enviaremos um link para redefinir sua senha.">
      {sent ? (
        <div>
          <div className="flex flex-col items-center text-center py-6">
            <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50 dark:bg-green-950/30">
              <CheckCircle2 className="h-8 w-8 text-heal-success" />
            </div>
            <h3 className="text-lg font-bold text-heal-ink dark:text-white mb-2">
              E-mail enviado!
            </h3>
            <p className="text-sm text-heal-muted leading-relaxed max-w-xs mb-6">
              Verifique sua caixa de entrada e siga as instrucoes para redefinir sua senha.
            </p>
            <Link
              to="/login"
              className="inline-flex items-center gap-2 text-sm font-semibold text-heal-blue hover:text-heal-blueDark transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              Voltar para o login
            </Link>
          </div>
        </div>
      ) : (
        <>
          <form className="space-y-5" onSubmit={handleSubmit(onSubmit)}>
            <Input
              label="E-mail cadastrado"
              type="email"
              autoComplete="email"
              icon={<Mail className="h-4 w-4" />}
              error={errors.email?.message}
              {...register('email')}
              disabled={isSubmitting}
            />

            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4">
                <p className="text-sm font-medium text-red-800">{error}</p>
              </div>
            )}

            <Button type="submit" className="w-full" size="lg" isLoading={isSubmitting}>
              Enviar link de recuperacao
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-heal-muted">
            <Link to="/login" className="inline-flex items-center gap-1 font-semibold text-heal-blue hover:text-heal-blueDark transition-colors">
              <ArrowLeft className="h-3.5 w-3.5" />
              Voltar para o login
            </Link>
          </p>
        </>
      )}
    </AuthLayout>
  );
}
