/**
 * Image Analysis Service — Upload para Firebase Storage + analise com IA
 *
 * Combina Firebase Storage para armazenamento de imagens,
 * Firestore para persistir resultados, e o backend HEAL+ para analise.
 */
import {
  addDoc,
  collection,
  doc,
  getDoc,
  getDocs,
  orderBy,
  query,
  serverTimestamp,
  where,
  limit,
} from "firebase/firestore";
import { ref, uploadBytes, getDownloadURL } from "firebase/storage";
import { db, storage } from "@/lib/firebase";
import type { NeuralAnalysisResult } from "@/services/ai/heal-ai-service";

// ─── Types ───────────────────────────────────────────────────
export type ImageAnalysis = {
  id: string;
  patientId?: string;
  imageUrl: string;
  filename: string;
  analysisResult: NeuralAnalysisResult | null;
  geminiAnalysis?: string;
  labels?: Array<{ description: string; confidence: number }>;
  createdAt: string;
  status: "pending" | "completed" | "failed";
};

// ─── Refs ────────────────────────────────────────────────────
const analysesRef = collection(db, "analyses");

// ─── Upload + Analise ────────────────────────────────────────
export async function uploadAndAnalyzeImage(
  imageFile: File,
  patientId?: string,
): Promise<ImageAnalysis> {
  const analysisId = crypto.randomUUID();
  const timestamp = new Date().toISOString();
  const storagePath = `analyses/${analysisId}/${imageFile.name}`;

  // 1. Upload para Firebase Storage
  let imageUrl = "";
  try {
    const storageRef = ref(storage, storagePath);
    const snapshot = await uploadBytes(storageRef, imageFile);
    imageUrl = await getDownloadURL(snapshot.ref);
  } catch (error) {
    console.error("[Storage] Upload falhou:", error);
    imageUrl = URL.createObjectURL(imageFile);
  }

  // 2. Analise com backend HEAL+ (via proxy Next.js)
  let analysisResult: NeuralAnalysisResult | null = null;
  try {
    const { analyzeWoundImage } = await import("@/services/ai/heal-ai-service");
    analysisResult = await analyzeWoundImage(imageFile);
  } catch (error) {
    console.error("[HEAL+] Analise backend falhou:", error);
  }

  // 3. Analise com Gemini Vision (Firebase AI Logic)
  let geminiAnalysis = "";
  try {
    const { analyzeImageWithAI } = await import(
      "@/services/firebase/ai-chat-service"
    );
    geminiAnalysis = await analyzeImageWithAI(imageFile);
  } catch (error) {
    console.error("[Gemini Vision] Analise falhou:", error);
  }

  // 4. Labeling com Gemini (equivalente a ML Kit Image Labeling)
  let labels: Array<{ description: string; confidence: number }> = [];
  try {
    const { geminiVisionModel } = await import("@/lib/firebase-ai");

    const buffer = await imageFile.arrayBuffer();
    const base64 = btoa(
      new Uint8Array(buffer).reduce(
        (data, byte) => data + String.fromCharCode(byte),
        "",
      ),
    );

    const labelResult = await geminiVisionModel.generateContent([
      "Identifique os elementos nesta imagem medica. Retorne APENAS um JSON: " +
        '{"labels":[{"description":"texto","confidence":0.95}]}. ' +
        "Inclua: tecidos, cores, texturas, objetos, anatomia, condicoes medicas.",
      {
        inlineData: {
          mimeType: imageFile.type || "image/jpeg",
          data: base64,
        },
      },
    ]);

    const text = labelResult.response.text().trim();
    const jsonStr = text.startsWith("```")
      ? text.split("\n").slice(1).join("\n").replace(/```$/, "").trim()
      : text;

    const parsed = JSON.parse(jsonStr);
    labels = parsed.labels || [];
  } catch (error) {
    console.error("[ML Labels] Labeling falhou:", error);
  }

  // 5. Salva resultado no Firestore
  const analysisDoc: Omit<ImageAnalysis, "id"> = {
    patientId,
    imageUrl,
    filename: imageFile.name,
    analysisResult,
    geminiAnalysis,
    labels,
    createdAt: timestamp,
    status: analysisResult || geminiAnalysis ? "completed" : "failed",
  };

  try {
    await addDoc(analysesRef, {
      ...analysisDoc,
      id: analysisId,
      serverTimestamp: serverTimestamp(),
    });
  } catch (error) {
    console.error("[Firestore] Salvar analise falhou:", error);
  }

  return { id: analysisId, ...analysisDoc };
}

// ─── Leitura ─────────────────────────────────────────────────
export async function getAnalysisHistory(
  patientId?: string,
  maxResults = 20,
): Promise<ImageAnalysis[]> {
  try {
    let q;
    if (patientId) {
      q = query(
        analysesRef,
        where("patientId", "==", patientId),
        orderBy("createdAt", "desc"),
        limit(maxResults),
      );
    } else {
      q = query(
        analysesRef,
        orderBy("createdAt", "desc"),
        limit(maxResults),
      );
    }

    const snapshot = await getDocs(q);
    return snapshot.docs.map((d) => {
      const data = d.data();
      return {
        id: d.id,
        patientId: data.patientId,
        imageUrl: data.imageUrl ?? "",
        filename: data.filename ?? "",
        analysisResult: data.analysisResult ?? null,
        geminiAnalysis: data.geminiAnalysis,
        labels: data.labels,
        createdAt: data.createdAt ?? "",
        status: data.status ?? "completed",
      };
    });
  } catch (error) {
    console.error("[Firestore] Buscar analises falhou:", error);
    return [];
  }
}

export async function getAnalysisById(
  id: string,
): Promise<ImageAnalysis | null> {
  try {
    const docRef = doc(db, "analyses", id);
    const snapshot = await getDoc(docRef);

    if (!snapshot.exists()) return null;

    const data = snapshot.data();
    return {
      id: snapshot.id,
      patientId: data.patientId,
      imageUrl: data.imageUrl ?? "",
      filename: data.filename ?? "",
      analysisResult: data.analysisResult ?? null,
      geminiAnalysis: data.geminiAnalysis,
      labels: data.labels,
      createdAt: data.createdAt ?? "",
      status: data.status ?? "completed",
    };
  } catch (error) {
    console.error("[Firestore] Buscar analise falhou:", error);
    return null;
  }
}
