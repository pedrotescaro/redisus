import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';

import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Textarea } from '../../components/ui/Textarea';
import type { Patient } from '../../lib/types';
import { patientSchema, type PatientFormValues } from './patientSchema';

interface PatientFormProps {
  patient?: Patient | null;
  onSubmit: (values: PatientFormValues) => Promise<void>;
  onCancel?: () => void;
}

const defaultValues: PatientFormValues = {
  name: '',
  phone: '',
  email: '',
  birthDate: '',
  notes: '',
  archived: false
};

export function PatientForm({ patient, onSubmit, onCancel }: PatientFormProps) {
  const {
    register,
    reset,
    handleSubmit,
    formState: { errors, isSubmitting }
  } = useForm<PatientFormValues>({ resolver: zodResolver(patientSchema), defaultValues });

  useEffect(() => {
    reset(
      patient
        ? {
            name: patient.name,
            phone: patient.phone,
            email: patient.email,
            birthDate: patient.birthDate,
            notes: patient.notes,
            archived: patient.archived
          }
        : defaultValues
    );
  }, [patient, reset]);

  return (
    <form className="grid gap-4" onSubmit={handleSubmit(onSubmit)}>
      <div className="grid gap-4 md:grid-cols-2">
        <Input label="Nome" error={errors.name?.message} {...register('name')} />
        <Input label="Telefone" error={errors.phone?.message} {...register('phone')} />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Input label="E-mail" type="email" error={errors.email?.message} {...register('email')} />
        <Input label="Data de nascimento" type="date" error={errors.birthDate?.message} {...register('birthDate')} />
      </div>
      <Textarea label="Observacoes" error={errors.notes?.message} {...register('notes')} />
      <label className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-zinc-200">
        <input type="checkbox" className="h-4 w-4 rounded border-heal-line text-heal-blue" {...register('archived')} />
        Paciente arquivado
      </label>
      <div className="flex justify-end gap-2">
        {onCancel ? (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancelar
          </Button>
        ) : null}
        <Button type="submit" isLoading={isSubmitting}>
          Salvar paciente
        </Button>
      </div>
    </form>
  );
}
