import { supabase } from '../../lib/supabase';
import { generateUUID } from '../../lib/uuid';
import type { Patient } from '../../lib/types';
import type { PatientFormValues } from './patientSchema';

export function subscribePatients(uid: string, onData: (patients: Patient[]) => void, onError?: (error: Error) => void) {
  const fetchPatients = async () => {
    const { data, error } = await supabase
      .from('patients')
      .select('*')
      .eq('user_id', uid)
      .order('created_at', { ascending: false });

    if (error) {
      if (onError) onError(new Error(error.message));
      return;
    }

    const mapped: Patient[] = (data || []).map(row => ({
      id: row.id,
      name: row.name,
      phone: row.phone || '',
      email: row.email || '',
      birthDate: row.birth_date || '',
      notes: row.notes || '',
      archived: row.archived || false,
      createdAt: row.created_at,
      updatedAt: row.updated_at
    }));

    onData(mapped);
  };

  fetchPatients();

  const channel = supabase
    .channel(`patients-changes-${uid}`)
    .on(
      'postgres_changes',
      { event: '*', schema: 'public', table: 'patients', filter: `user_id=eq.${uid}` },
      () => {
        void fetchPatients();
      }
    )
    .subscribe();

  return () => {
    void supabase.removeChannel(channel);
  };
}

export async function getPatient(uid: string, patientId: string): Promise<Patient | null> {
  const { data, error } = await supabase
    .from('patients')
    .select('*')
    .eq('id', patientId)
    .eq('user_id', uid)
    .single();

  if (error || !data) return null;

  return {
    id: data.id,
    name: data.name,
    phone: data.phone || '',
    email: data.email || '',
    birthDate: data.birth_date || '',
    notes: data.notes || '',
    archived: data.archived || false,
    createdAt: data.created_at,
    updatedAt: data.updated_at
  };
}

export async function createPatient(uid: string, values: PatientFormValues): Promise<string> {
  const patientId = generateUUID();
  const { error } = await supabase
    .from('patients')
    .insert({
      id: patientId,
      user_id: uid,
      name: values.name,
      phone: values.phone || '',
      email: values.email || '',
      birth_date: values.birthDate || '',
      notes: values.notes || '',
      archived: values.archived || false
    });

  if (error) throw new Error(error.message);
  return patientId;
}

export async function updatePatient(uid: string, patientId: string, values: PatientFormValues): Promise<void> {
  const { error } = await supabase
    .from('patients')
    .update({
      name: values.name,
      phone: values.phone || '',
      email: values.email || '',
      birth_date: values.birthDate || '',
      notes: values.notes || '',
      archived: values.archived || false,
      updated_at: new Date().toISOString()
    })
    .eq('id', patientId)
    .eq('user_id', uid);

  if (error) throw new Error(error.message);
}

export async function setPatientArchived(uid: string, patientId: string, archived: boolean): Promise<void> {
  const { error } = await supabase
    .from('patients')
    .update({
      archived,
      updated_at: new Date().toISOString()
    })
    .eq('id', patientId)
    .eq('user_id', uid);

  if (error) throw new Error(error.message);
}
