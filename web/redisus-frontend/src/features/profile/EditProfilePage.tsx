import { zodResolver } from '@hookform/resolvers/zod';
import { Upload } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';

import { useAuth } from '../../app/providers/AuthProvider';
import { UserAvatar } from '../../components/profile/UserAvatar';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/Card';
import { Input } from '../../components/ui/input';
import { PageHeader } from '../../components/ui/PageHeader';
import { profileSchema, type ProfileFormValues, updateProfileData, uploadProfilePhoto } from './profileService';

export function EditProfilePage() {
  const { user, profile } = useAuth();
  const [message, setMessage] = useState('');
  const [photoError, setPhotoError] = useState('');
  const {
    register,
    reset,
    handleSubmit,
    formState: { errors, isSubmitting }
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: { displayName: '', email: '', professionalArea: '', clinicName: '', phone: '' }
  });

  useEffect(() => {
    reset({
      displayName: profile?.displayName || user?.displayName || '',
      email: profile?.email || user?.email || '',
      professionalArea: profile?.professionalArea || '',
      clinicName: profile?.clinicName || '',
      phone: profile?.phone || ''
    });
  }, [profile, reset, user]);

  const onSubmit = async (values: ProfileFormValues) => {
    if (!user) return;
    await updateProfileData(user.uid, values);
    setMessage('Perfil atualizado.');
  };

  const handlePhoto = async (fileList: FileList | null) => {
    if (!user || !fileList?.[0]) return;
    setPhotoError('');
    try {
      await uploadProfilePhoto(user.uid, fileList[0]);
      setMessage('Foto enviada para o Supabase Storage.');
    } catch (error) {
      setPhotoError(error instanceof Error ? error.message : 'Não foi possível enviar a foto.');
    }
  };

  const displayName = profile?.displayName || user?.displayName || 'Profissional';
  const photoURL = profile?.photoURL || user?.photoURL;

  return (
    <div className="flex flex-col xl:flex-row min-h-screen min-w-0 bg-white dark:bg-[#0c0c0e]">
      {/* Coluna Central */}
      <div className="flex-grow max-w-2xl w-full border-r border-heal-line dark:border-zinc-800/60 min-h-screen flex flex-col min-w-0">
        <PageHeader showBack title="Editar perfil" description="Atualize seus dados pessoais e profissionais" />
        
        <div className="p-4 sm:p-6 space-y-6">
          <div className="flex items-center gap-4 select-none">
            <UserAvatar
              name={displayName}
              src={photoURL}
              imageClassName="h-16 w-16 rounded-xl object-cover ring-2 ring-heal-blue/20"
              fallbackClassName="flex h-16 w-16 items-center justify-center rounded-xl bg-heal-softBlue/60 text-lg font-black text-heal-blue dark:bg-blue-950/40"
            />
            <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-heal-line/75 bg-white px-4 py-2 text-xs font-bold text-heal-ink hover:bg-slate-50 transition-colors dark:border-zinc-800 dark:bg-zinc-900 dark:text-white">
              <Upload className="h-4 w-4 text-heal-muted" />
              Enviar foto
              <input type="file" accept="image/*" className="hidden" onChange={event => void handlePhoto(event.target.files)} />
            </label>
          </div>
          {photoError ? <div className="mt-3 rounded-xl bg-red-50/70 dark:bg-red-950/20 px-3 py-2 text-xs font-bold text-red-700 dark:text-red-300 border border-red-200/50 dark:border-red-950/50">{photoError}</div> : null}

          <form className="mt-6 space-y-4" onSubmit={handleSubmit(onSubmit)}>
            <Input label="Nome" error={errors.displayName?.message} {...register('displayName')} />
            <Input label="E-mail visual" type="email" error={errors.email?.message} {...register('email')} />
            <Input label="Área de atuação" error={errors.professionalArea?.message} {...register('professionalArea')} />
            <Input label="Instituição ou clínica" error={errors.clinicName?.message} {...register('clinicName')} />
            <Input label="Telefone" error={errors.phone?.message} {...register('phone')} />
            {message ? <div className="rounded-xl bg-emerald-50/70 dark:bg-emerald-950/20 px-3 py-2 text-xs font-bold text-emerald-700 dark:text-emerald-300 border border-emerald-200/50 dark:border-emerald-950/50">{message}</div> : null}
            <Button type="submit" size="sm" isLoading={isSubmitting}>Salvar perfil</Button>
          </form>
        </div>
      </div>
    </div>
  );
}
