import { z } from 'zod';
import { supabase } from '../../lib/supabase';
import { generateUUID } from '../../lib/uuid';
import type { Appointment } from '../../lib/types';

export const appointmentSchema = z.object({
  patientId: z.string().min(1, 'Selecione um paciente.'),
  patientName: z.string().min(1, 'Paciente inválido.'),
  date: z.string().min(1, 'Informe a data.'),
  time: z.string().min(4, 'Informe o horário.'),
  type: z.string().min(2, 'Informe o tipo.'),
  status: z.enum(['Confirmado', 'Pendente', 'Cancelado', 'Realizado']),
  notes: z.string().max(1000).optional().default('')
});

export type AppointmentFormValues = z.infer<typeof appointmentSchema>;

export function subscribeAppointments(uid: string, onData: (appointments: Appointment[]) => void, onError?: (error: Error) => void) {
  const fetchAppointments = async () => {
    const { data, error } = await supabase
      .from('appointments')
      .select('*')
      .eq('user_id', uid)
      .order('date', { ascending: true });

    if (error) {
      if (onError) onError(new Error(error.message));
      return;
    }

    const mapped: Appointment[] = (data || []).map(row => ({
      id: row.id,
      patientId: row.patient_id,
      patientName: row.patient_name,
      date: row.date,
      time: row.time,
      type: row.type,
      status: (row.status as Appointment['status']) || 'Pendente',
      notes: row.notes || '',
      createdAt: row.created_at,
      updatedAt: row.updated_at
    })).sort((a, b) => a.date.localeCompare(b.date) || a.time.localeCompare(b.time));

    onData(mapped);
  };

  fetchAppointments();

  const channel = supabase
    .channel(`appointments-changes-${uid}`)
    .on(
      'postgres_changes',
      { event: '*', schema: 'public', table: 'appointments', filter: `user_id=eq.${uid}` },
      () => {
        void fetchAppointments();
      }
    )
    .subscribe();

  return () => {
    void supabase.removeChannel(channel);
  };
}

export async function createAppointment(uid: string, values: AppointmentFormValues): Promise<string> {
  const appointmentId = generateUUID();
  const { error } = await supabase
    .from('appointments')
    .insert({
      id: appointmentId,
      user_id: uid,
      patient_id: values.patientId,
      patient_name: values.patientName,
      date: values.date,
      time: values.time,
      type: values.type,
      status: values.status,
      notes: values.notes || ''
    });

  if (error) throw new Error(error.message);
  return appointmentId;
}

export async function updateAppointment(uid: string, appointmentId: string, values: AppointmentFormValues): Promise<void> {
  const { error } = await supabase
    .from('appointments')
    .update({
      patient_id: values.patientId,
      patient_name: values.patientName,
      date: values.date,
      time: values.time,
      type: values.type,
      status: values.status,
      notes: values.notes || '',
      updated_at: new Date().toISOString()
    })
    .eq('id', appointmentId)
    .eq('user_id', uid);

  if (error) throw new Error(error.message);
}

export async function deleteAppointment(uid: string, appointmentId: string): Promise<void> {
  const { error } = await supabase
    .from('appointments')
    .delete()
    .eq('id', appointmentId)
    .eq('user_id', uid);

  if (error) throw new Error(error.message);
}
