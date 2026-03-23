"use server";

import { gemini20Flash, googleAI } from "@genkit-ai/googleai";
import { genkit } from "genkit";

// Usa a chave que ja esta no .env.local
const apiKey =
  process.env.GOOGLE_GENAI_API_KEY ||
  process.env.NEXT_PUBLIC_FIREBASE_API_KEY;

const ai = genkit({
  plugins: [googleAI({ apiKey })],
  model: gemini20Flash,
});

const chatSystemPrompt =
  "Você é o assistente de IA HEAL+ da plataforma REDISUS (Rede Digital do SUS). " +
  "Especialista em estomaterapia, analise de feridas cronicas, cicatrizacao " +
  "e cuidados clinicos. Responda em portugues brasileiro, de forma tecnica " +
  "mas acessivel a profissionais de saude. Seja conciso e direto. " +
  "Quando relevante, cite protocolos clinicos e escalas como PUSH, BWAT e Braden.";

const visionSystemPrompt =
  "Você é um especialista em análise de imagens médicas de feridas. " +
  "Analise as imagens fornecidas e identifique: tipo de tecido " +
  "(necrose, esfacelo, granulação, epitelização), características da ferida, " +
  "bordas, sinais de infecção, e sugestões de conduta. " +
  "Responda em português brasileiro, sempre em formato estruturado.";

export async function generateChatResponse(
  history: { role: string; content: string }[],
  message: string
) {
  try {
    const formattedHistory = history.map((msg) => ({
      role: (msg.role === "assistant" ? "model" : "user") as "user" | "model",
      content: [{ text: msg.content }],
    }));

    const requestParams: any = {
      system: chatSystemPrompt,
      messages: [
        ...formattedHistory,
        { role: "user", content: [{ text: message }] },
      ],
    };

    const { text } = await ai.generate(requestParams);

    return text;
  } catch (error) {
    console.error("[Genkit Action] Erro no chat:", error);
    throw error;
  }
}


export async function generateVisionResponse(
  base64Image: string,
  mimeType: string,
  customPrompt?: string
) {
  try {
    const promptText =
      customPrompt ||
      "Analise esta imagem de ferida/lesao. Identifique:\n" +
        "1. Tipo de tecido predominante (necrose, esfacelo, granulacao, epitelizacao)\n" +
        "2. Caracteristicas visiveis\n" +
        "3. Sinais de infeccao (se houver)\n" +
        "4. Sugestao de conduta clinica\n" +
        "5. Avaliacao geral do estado da ferida";

    const dataUri = `data:${mimeType};base64,${base64Image}`;

    const { text } = await ai.generate({
      system: visionSystemPrompt,
      prompt: [
        { text: promptText },
        { media: { url: dataUri } },
      ],
    });

    return text;
  } catch (error) {
    console.error("[Genkit Action] Erro na visao:", error);
    throw error;
  }
}
