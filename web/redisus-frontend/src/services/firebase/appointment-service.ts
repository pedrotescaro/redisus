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

export type AppointmentStatus = "pendente" | "em_andamento" | "concluida";

export type Appointment = {
  id: string;
  date: string;
  time: string;
  patient: string;
  etiology: string;
  region: string;
  complexity?: "Alta Complexidade" | "Moderada" | "Baixa";
  status: AppointmentStatus;
};

export type NewAppointmentPayload = Omit<Appointment, "id">;

function appointmentsColRef(uid: string) {
  return collection(db, "users", uid, "appointments");
}

export async function listAppointments(uid: string): Promise<Appointment[]> {
  const q = query(appointmentsColRef(uid), orderBy("date", "asc"));
  const snapshot = await getDocs(q);

  return snapshot.docs.map((d) => {
    const data = d.data() as Omit<Appointment, "id">;
    return { id: d.id, ...data };
  });
}

export async function createAppointment(
  uid: string,
  payload: NewAppointmentPayload,
): Promise<string> {
  const docRef = await addDoc(appointmentsColRef(uid), {
    ...payload,
    createdAt: serverTimestamp(),
  });
  return docRef.id;
}

export async function updateAppointmentStatus(
  uid: string,
  appointmentId: string,
  status: AppointmentStatus,
): Promise<void> {
  const appointmentDoc = doc(db, "users", uid, "appointments", appointmentId);
  await updateDoc(appointmentDoc, { status, updatedAt: serverTimestamp() });
}

export async function deleteAppointment(
  uid: string,
  appointmentId: string,
): Promise<void> {
  const appointmentDoc = doc(db, "users", uid, "appointments", appointmentId);
  await deleteDoc(appointmentDoc);
}
