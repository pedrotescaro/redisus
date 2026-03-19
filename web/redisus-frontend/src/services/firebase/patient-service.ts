import {
  addDoc,
  collection,
  deleteDoc,
  doc,
  getDocs,
  orderBy,
  query,
  serverTimestamp,
  updateDoc,
} from "firebase/firestore";
import { db } from "@/lib/firebase";
import type { NewPatientPayload, Patient, UpdatePatientPayload } from "@/types/patient";

const patientsRef = collection(db, "patients");

export async function listPatients(): Promise<Patient[]> {
  const snapshot = await getDocs(query(patientsRef, orderBy("name", "asc")));

  return snapshot.docs.map((item) => {
    const data = item.data() as Omit<Patient, "id">;

    return {
      id: item.id,
      name: data.name,
      age: data.age,
      clinicalHistory: data.clinicalHistory,
      createdAt: data.createdAt,
      updatedAt: data.updatedAt,
    };
  });
}

export async function createPatient(payload: NewPatientPayload) {
  return addDoc(patientsRef, {
    ...payload,
    createdAt: serverTimestamp(),
    updatedAt: serverTimestamp(),
  });
}

export async function updatePatient(id: string, payload: UpdatePatientPayload) {
  const patientDoc = doc(db, "patients", id);

  return updateDoc(patientDoc, {
    ...payload,
    updatedAt: serverTimestamp(),
  });
}

export async function deletePatient(id: string) {
  const patientDoc = doc(db, "patients", id);
  return deleteDoc(patientDoc);
}
