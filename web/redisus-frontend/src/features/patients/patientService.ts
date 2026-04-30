import {
  addDoc,
  collection,
  doc,
  getDoc,
  onSnapshot,
  orderBy,
  query,
  serverTimestamp,
  updateDoc
} from 'firebase/firestore';

import { db } from '../../lib/firebase';
import { patientPath, patientsPath } from '../../lib/firestorePaths';
import type { Patient } from '../../lib/types';
import type { PatientFormValues } from './patientSchema';

const mapPatient = (id: string, data: Record<string, unknown>): Patient => ({
  id,
  name: String(data.name || ''),
  phone: String(data.phone || ''),
  email: String(data.email || ''),
  birthDate: String(data.birthDate || ''),
  notes: String(data.notes || ''),
  archived: Boolean(data.archived),
  createdAt: data.createdAt as Patient['createdAt'],
  updatedAt: data.updatedAt as Patient['updatedAt']
});

export function subscribePatients(uid: string, onData: (patients: Patient[]) => void, onError?: (error: Error) => void) {
  return onSnapshot(
    query(collection(db, patientsPath(uid)), orderBy('createdAt', 'desc')),
    snapshot => onData(snapshot.docs.map(item => mapPatient(item.id, item.data()))),
    onError
  );
}

export async function getPatient(uid: string, patientId: string) {
  const snapshot = await getDoc(doc(db, patientPath(uid, patientId)));
  return snapshot.exists() ? mapPatient(snapshot.id, snapshot.data()) : null;
}

export async function createPatient(uid: string, values: PatientFormValues) {
  const ref = await addDoc(collection(db, patientsPath(uid)), {
    ...values,
    notes: values.notes || '',
    createdAt: serverTimestamp(),
    updatedAt: serverTimestamp()
  });
  return ref.id;
}

export async function updatePatient(uid: string, patientId: string, values: PatientFormValues) {
  await updateDoc(doc(db, patientPath(uid, patientId)), {
    ...values,
    notes: values.notes || '',
    updatedAt: serverTimestamp()
  });
}

export async function setPatientArchived(uid: string, patientId: string, archived: boolean) {
  await updateDoc(doc(db, patientPath(uid, patientId)), {
    archived,
    updatedAt: serverTimestamp()
  });
}
