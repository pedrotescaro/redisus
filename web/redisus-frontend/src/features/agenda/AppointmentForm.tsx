import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';

import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Select } from '../../components/ui/Select';
import { Textarea } from '../../components/ui/textarea';
import { FORM_OPTIONS } from '../../lib/constants';
import { todayISO } from '../../lib/date';
import type { Appointment, Patient } from '../../lib/types';
import { appointmentSchema, type AppointmentFormValues } from './agendaService';

interface AppointmentFormProps {
  patients: Patient[];
  appointment?: Appointment | null;
  defaultPatientId?: string;
  onSubmit: (values: AppointmentFormValues) => Promise<void>;
  onCancel?: () => void;
}

export function AppointmentForm({ patients, appointment, defaultPatientId, onSubmit, onCancel }: AppointmentFormProps) {
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isSubmitting }
  } = useForm<AppointmentFormValues>({
    resolver: zodResolver(appointmentSchema),
    defaultValues: {
      patientId: '',
      patientName: '',
      date: todayISO(),
      time: '08:00',
      type: 'Retorno',
      status: 'Pendente',
      notes: ''
    }
  });

  const selectedPatientId = watch('patientId');

  useEffect(() => {
    if (appointment) reset(appointment);
    else if (defaultPatientId) setValue('patientId', defaultPatientId);
  }, [appointment, defaultPatientId, reset, setValue]);

  useEffect(() => {
    const patient = patients.find(item => item.id === selectedPatientId);
    setValue('patientName', patient?.name || '', { shouldValidate: true });
  }, [patients, selectedPatientId, setValue]);

  return (
    <form className="grid gap-4" onSubmit={handleSubmit(onSubmit)}>
      <Select
        label="Paciente"
        options={patients.map(patient => patient.name)}
        value={patients.find(p => p.id === selectedPatientId)?.name || ''}
        onChange={event => {
          const patient = patients.find(item => item.name === event.target.value);
          setValue('patientId', patient?.id || '', { shouldValidate: true });
        }}
        error={errors.patientId?.message}
      />
      <input type="hidden" {...register('patientId')} />
      <input type="hidden" {...register('patientName')} />
      <div className="grid gap-4 md:grid-cols-2">
        <Input label="Data" type="date" error={errors.date?.message} {...register('date')} />
        <Input label="Hora" type="time" error={errors.time?.message} {...register('time')} />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Select label="Tipo" options={FORM_OPTIONS.appointmentTypes} error={errors.type?.message} {...register('type')} />
        <Select label="Status" options={FORM_OPTIONS.appointmentStatuses} error={errors.status?.message} {...register('status')} />
      </div>
      <Textarea label="Observacoes" error={errors.notes?.message} {...register('notes')} />
      <div className="flex justify-end gap-2">
        {onCancel ? <Button type="button" variant="secondary" onClick={onCancel}>Cancelar</Button> : null}
        <Button type="submit" isLoading={isSubmitting}>Salvar atendimento</Button>
      </div>
    </form>
  );
}
