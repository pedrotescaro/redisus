/**
 * Firebase AI Logic — Integracao com Gemini via Firebase SDK
 *
 * Usa o modulo `firebase/ai` para acessar a API Gemini diretamente
 * do frontend, sem necessidade de servidor intermediario para chat simples.
 */
import { getAI, getGenerativeModel, GoogleAIBackend } from "firebase/ai";
import { app } from "@/lib/firebase";

// Inicializa o backend do Gemini Developer API
const ai = getAI(app, { backend: new GoogleAIBackend() });

// Modelo generativo para chat
export const geminiModel = getGenerativeModel(ai, {
  model: "gemini-2.0-flash",
  systemInstruction: {
    role: "system",
    parts: [
      {
        text:
          "Voce e o assistente de IA HEAL+ da plataforma REDISUS (Rede Digital do SUS). " +
          "Especialista em estomaterapia, analise de feridas cronicas, cicatrizacao " +
          "e cuidados clinicos. Responda em portugues brasileiro, de forma tecnica " +
          "mas acessivel a profissionais de saude. Seja conciso e direto. " +
          "Quando relevante, cite protocolos clinicos e escalas como PUSH, BWAT e Braden.",
      },
    ],
  },
});

// Modelo para analise de imagens (visao)
export const geminiVisionModel = getGenerativeModel(ai, {
  model: "gemini-2.0-flash",
  systemInstruction: {
    role: "system",
    parts: [
      {
        text:
          "Voce e um especialista em analise de imagens medicas de feridas. " +
          "Analise as imagens fornecidas e identifique: tipo de tecido " +
          "(necrose, esfacelo, granulacao, epitelizacao), caracteristicas da ferida, " +
          "bordas, sinais de infeccao, e sugestoes de conduta. " +
          "Responda em portugues brasileiro, sempre em formato estruturado.",
      },
    ],
  },
});

export { ai };
