import {
  addDoc,
  collection,
  deleteDoc,
  doc,
  getDoc,
  getDocs,
  limit,
  orderBy,
  query,
  serverTimestamp,
  setDoc,
} from "firebase/firestore";
import { db } from "@/lib/firebase";

const DRAFT_DOC_ID = "current";

function draftDocRef(uid: string) {
  return doc(db, "users", uid, "evaluation_drafts", DRAFT_DOC_ID);
}

function historyColRef(uid: string) {
  return collection(db, "users", uid, "evaluation_history");
}

// ---------------------------------------------------------------------------
// Drafts
// ---------------------------------------------------------------------------

export async function saveDraft(
  uid: string,
  data: Record<string, unknown>,
): Promise<void> {
  await setDoc(draftDocRef(uid), {
    ...data,
    updatedAt: serverTimestamp(),
  });
}

export async function loadDraft(
  uid: string,
): Promise<Record<string, unknown> | null> {
  const snapshot = await getDoc(draftDocRef(uid));
  if (!snapshot.exists()) return null;
  return snapshot.data() as Record<string, unknown>;
}

export async function deleteDraft(uid: string): Promise<void> {
  await deleteDoc(draftDocRef(uid));
}

// ---------------------------------------------------------------------------
// History
// ---------------------------------------------------------------------------

export async function addHistoryEntry(
  uid: string,
  entry: Record<string, unknown>,
): Promise<string> {
  const docRef = await addDoc(historyColRef(uid), {
    ...entry,
    createdAt: serverTimestamp(),
  });
  return docRef.id;
}

export async function listHistory(
  uid: string,
  maxItems = 50,
): Promise<Array<Record<string, unknown> & { id: string }>> {
  const q = query(
    historyColRef(uid),
    orderBy("createdAt", "desc"),
    limit(maxItems),
  );

  const snapshot = await getDocs(q);
  return snapshot.docs.map((d) => ({ id: d.id, ...d.data() }));
}
