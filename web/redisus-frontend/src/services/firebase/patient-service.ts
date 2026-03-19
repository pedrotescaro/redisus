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
const PATIENTS_CACHE_TTL_MS = 60_000;

let patientsCache: Patient[] | null = null;
let patientsCacheAt = 0;

function sortPatientsByName(data: Patient[]) {
  return [...data].sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));
}

export async function listPatients(options?: { forceRefresh?: boolean }): Promise<Patient[]> {
  const forceRefresh = options?.forceRefresh ?? false;
  const cacheFresh = Date.now() - patientsCacheAt < PATIENTS_CACHE_TTL_MS;

  if (!forceRefresh && patientsCache && cacheFresh) {
    return patientsCache;
  }

  const snapshot = await getDocs(query(patientsRef, orderBy("name", "asc")));

  const parsed = snapshot.docs.map((item) => {
    const data = item.data() as Omit<Patient, "id">;

    return {
      id: item.id,
      name: data.name,
      birthDate: data.birthDate ?? "",
      phone: data.phone ?? "",
      email: data.email ?? "",
      profession: data.profession ?? "",
      maritalStatus: data.maritalStatus ?? "",
      age: data.age,
      clinicalHistory: data.clinicalHistory,
      hppItems: data.hppItems ?? [],
      comorbidities: data.comorbidities ?? [],
      medicationsInUse: data.medicationsInUse ?? [],
      createdAt: data.createdAt,
      updatedAt: data.updatedAt,
    };
  });

  patientsCache = parsed;
  patientsCacheAt = Date.now();

  return parsed;
}

export function primePatientsCache(data: Patient[]) {
  patientsCache = sortPatientsByName(data);
  patientsCacheAt = Date.now();
}

export function invalidatePatientsCache() {
  patientsCache = null;
  patientsCacheAt = 0;
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
