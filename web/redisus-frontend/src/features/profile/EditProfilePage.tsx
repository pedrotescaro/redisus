import { zodResolver } from '@hookform/resolvers/zod';
import { Upload } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';

import { useAuth } from '../../app/providers/AuthProvider';
import { UserAvatar } from '../../components/profile/UserAvatar';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/Card';
import { Input } from '../../components/ui/input';
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
      setMessage('Foto enviada para o Firebase Storage.');
    } catch (error) {
      setPhotoError(error instanceof Error ? error.message : 'Não foi possível enviar a foto.');
    }
  };

  const displayName = profile?.displayName || user?.displayName || 'Profissional';
  const photoURL = profile?.photoURL || user?.photoURL;

  return (
    <Card className="mx-auto max-w-2xl">
      <h2 className="text-2xl font-black text-heal-ink dark:text-white">Editar perfil</h2>
      <div className="mt-5 flex items-center gap-4">
        <UserAvatar
          name={displayName}
          src={photoURL}
          imageClassName="h-20 w-20 rounded-full object-cover"
          fallbackClassName="flex h-20 w-20 items-center justify-center rounded-full bg-blue-100 text-xl font-black text-heal-blue dark:bg-blue-950"
        />
        <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-heal-line bg-white px-4 py-2 text-sm font-semibold text-heal-ink hover:bg-slate-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white">
          <Upload className="h-4 w-4" />
          Enviar foto
          <input type="file" accept="image/*" className="hidden" onChange={event => void handlePhoto(event.target.files)} />
        </label>
      </div>
      {photoError ? <div className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-700">{photoError}</div> : null}

      <form className="mt-6 space-y-4" onSubmit={handleSubmit(onSubmit)}>
        <Input label="Nome" error={errors.displayName?.message} {...register('displayName')} />
        <Input label="E-mail visual" type="email" error={errors.email?.message} {...register('email')} />
        <Input label="Área de atuação" error={errors.professionalArea?.message} {...register('professionalArea')} />
        <Input label="Instituição ou clínica" error={errors.clinicName?.message} {...register('clinicName')} />
        <Input label="Telefone" error={errors.phone?.message} {...register('phone')} />
        {message ? <div className="rounded-lg bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700">{message}</div> : null}
        <Button type="submit" isLoading={isSubmitting}>Salvar perfil</Button>
      </form>
    </Card>
  );
}
