import {
  addDoc,
  collection,
  deleteDoc,
  doc,
  onSnapshot,
  orderBy,
  query,
  serverTimestamp,
  updateDoc
} from 'firebase/firestore';
import { z } from 'zod';

import { db } from '../../lib/firebase';
import { appointmentPath, appointmentsPath } from '../../lib/firestorePaths';
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

const mapAppointment = (id: string, data: Record<string, unknown>): Appointment => ({
  id,
  patientId: String(data.patientId || ''),
  patientName: String(data.patientName || ''),
  date: String(data.date || ''),
  time: String(data.time || ''),
  type: String(data.type || ''),
  status: (data.status as Appointment['status']) || 'Pendente',
  notes: String(data.notes || ''),
  createdAt: data.createdAt as Appointment['createdAt'],
  updatedAt: data.updatedAt as Appointment['updatedAt']
});

export function subscribeAppointments(uid: string, onData: (appointments: Appointment[]) => void, onError?: (error: Error) => void) {
  return onSnapshot(
    query(collection(db, appointmentsPath(uid)), orderBy('date', 'asc')),
    snapshot =>
      onData(
        snapshot.docs
          .map(item => mapAppointment(item.id, item.data()))
          .sort((a, b) => a.date.localeCompare(b.date) || a.time.localeCompare(b.time))
      ),
    onError
  );
}

export async function createAppointment(uid: string, values: AppointmentFormValues) {
  const ref = await addDoc(collection(db, appointmentsPath(uid)), {
    ...values,
    notes: values.notes || '',
    createdAt: serverTimestamp(),
    updatedAt: serverTimestamp()
  });
  return ref.id;
}

export async function updateAppointment(uid: string, appointmentId: string, values: AppointmentFormValues) {
  await updateDoc(doc(db, appointmentPath(uid, appointmentId)), {
    ...values,
    notes: values.notes || '',
    updatedAt: serverTimestamp()
  });
}

export async function deleteAppointment(uid: string, appointmentId: string) {
  await deleteDoc(doc(db, appointmentPath(uid, appointmentId)));
}
