import { zodResolver } from '@hookform/resolvers/zod';
import { Building2, Phone, Rocket, Stethoscope } from 'lucide-react';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { Navigate, useNavigate } from 'react-router-dom';

import { useAuth } from '../../app/providers/AuthProvider';
import { BrandLogo } from '../../components/brand/BrandLogo';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { updateUserProfile } from './authService';
import { onboardingSchema, type OnboardingFormValues } from './authSchema';

const areaOptions = ['Enfermagem', 'Medicina', 'Fisioterapia', 'Nutrição', 'Podologia', 'Outra área'];
const themeOptions = ['light', 'dark'];

export function OnboardingPage() {
  const { user, profile, loading } = useAuth();
  const navigate = useNavigate();
  const {
    register,
    reset,
    handleSubmit,
    formState: { errors, isSubmitting }
  } = useForm<OnboardingFormValues>({
    resolver: zodResolver(onboardingSchema),
    defaultValues: {
      professionalName: '',
      professionalArea: '',
      clinicName: '',
      phone: '',
      theme: 'light'
    }
  });

  useEffect(() => {
    reset({
      professionalName: profile?.displayName || user?.displayName || '',
      professionalArea: profile?.professionalArea || '',
      clinicName: profile?.clinicName || '',
      phone: profile?.phone || '',
      theme: profile?.settings?.theme || 'light'
    });
  }, [profile, reset, user]);

  if (!loading && !user) return <Navigate to="/login" replace />;
  if (profile?.onboardingCompleted) return <Navigate to="/dashboard" replace />;

  const onSubmit = async (values: OnboardingFormValues) => {
    if (!user) return;
    await updateUserProfile(user.uid, {
      displayName: values.professionalName,
      professionalArea: values.professionalArea,
      clinicName: values.clinicName || '',
      phone: values.phone || '',
      onboardingCompleted: true,
      settings: {
        ...(profile?.settings || {
          notificationsEnabled: true,
          emailNotificationsEnabled: true,
          agendaRemindersEnabled: true,
          hideEmailPreview: false,
          showProfilePhoto: true
        }),
        theme: values.theme
      }
    });
    navigate('/dashboard', { replace: true });
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-heal-canvas px-4 py-10 dark:bg-zinc-950">
      <Card className="w-full max-w-2xl p-8">
        <BrandLogo className="mb-8" />
        <p className="text-xs font-black uppercase tracking-[0.18em] text-heal-teal">Configuração inicial</p>
        <h1 className="mt-2 text-3xl font-black text-heal-ink dark:text-white">Comece com seu perfil profissional</h1>
        <p className="mt-2 text-sm leading-6 text-heal-muted dark:text-zinc-400">
          Esses dados aparecem no perfil, relatórios e assinatura clínica. Você pode editar depois.
        </p>

        <form className="mt-8 grid gap-4 md:grid-cols-2" onSubmit={handleSubmit(onSubmit)}>
          <Input
            className="md:col-span-2"
            label="Nome profissional"
            icon={<Stethoscope className="h-4 w-4" />}
            error={errors.professionalName?.message}
            {...register('professionalName')}
          />
          <Select label="Área de atuação" options={areaOptions} placeholder="Selecione" error={errors.professionalArea?.message} {...register('professionalArea')} />
          <Select label="Preferência de tema" options={themeOptions} error={errors.theme?.message} {...register('theme')} />
          <Input label="Instituição ou clínica" icon={<Building2 className="h-4 w-4" />} {...register('clinicName')} />
          <Input label="Telefone" type="tel" icon={<Phone className="h-4 w-4" />} {...register('phone')} />
          <div className="md:col-span-2">
            <Button type="submit" size="lg" icon={<Rocket className="h-4 w-4" />} isLoading={isSubmitting}>
              Começar agora
            </Button>
          </div>
        </form>
      </Card>
    </main>
  );
}
