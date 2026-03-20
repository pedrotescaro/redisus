import { addDoc, collection, serverTimestamp } from "firebase/firestore";
import { auth, db } from "@/lib/firebase";

type SyncEvaluationPayload = {
  apiEvaluationId: string;
  patientId: string;
  patientName: string;
  evaluationDate: string;
  woundType: string;
  woundLocation: string;
  clinicalDescription: string;
  pushScore: number;
  bradenScore: number;
  bwatScore: number;
  photoCount: number;
  timersPayload: Record<string, unknown>;
};

const evaluationsRef = collection(db, "clinical_evaluations");

export async function syncEvaluationToFirebase(payload: SyncEvaluationPayload) {
  const user = auth.currentUser;
  if (!user) {
    throw new Error("Usuário não autenticado no Firebase para sincronizar avaliação.");
  }

  return addDoc(evaluationsRef, {
    ...payload,
    uid: user.uid,
    userEmail: user.email ?? null,
    source: "clinical-api",
    syncedAt: serverTimestamp(),
    createdAt: serverTimestamp(),
    updatedAt: serverTimestamp(),
  });
}
