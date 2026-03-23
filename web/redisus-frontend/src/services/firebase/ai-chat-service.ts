/**
 * AI Chat Service — Servico de chat IA com persistencia Firestore
 *
 * Combina Firebase AI Logic (Gemini) com Firestore para persistir conversas.
 */
import {
  addDoc,
  collection,
  deleteDoc,
  doc,
  getDocs,
  orderBy,
  query,
  serverTimestamp,
  limit,
} from "firebase/firestore";
import { db } from "@/lib/firebase";

// ─── Types ───────────────────────────────────────────────────
export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  imageUrl?: string;
};

export type Conversation = {
  id: string;
  lastMessage: string;
  updatedAt: string;
  messageCount: number;
};

// ─── Refs ────────────────────────────────────────────────────
const conversationsRef = collection(db, "ai_conversations");

// ─── Chat via Server Action (Genkit) ───────────
export async function sendChatMessage(
  message: string,
  conversationId?: string,
): Promise<{ response: string; conversationId: string }> {
  const convId = conversationId || crypto.randomUUID();

  let aiResponse: string;

  // Carrega historico recente para contexto
  let prevMessages: ChatMessage[] = [];
  try {
    prevMessages = conversationId
      ? await getConversationMessages(conversationId, 10)
      : [];
  } catch {
    // sem historico — continua normalmente
  }

  try {
    const { generateChatResponse } = await import("@/app/actions/genkit-actions");
    
    // Chama a Server Action do Genkit passando o historico
    aiResponse = await generateChatResponse(
      prevMessages.map((msg) => ({
        role: msg.role,
        content: msg.content,
      })),
      message
    );
  } catch (error) {
    console.error("[AI Chat] Erro Genkit, usando fallback:", error);
    aiResponse = getFallbackResponse(message);
  }

  // Salva no Firestore
  try {
    const convDocRef = doc(db, "ai_conversations", convId);
    const msgColRef = collection(convDocRef, "messages");
    const now = new Date().toISOString();

    // Salva mensagem do usuario
    await addDoc(msgColRef, {
      role: "user",
      content: message,
      timestamp: now,
    });

    // Salva resposta do assistente
    await addDoc(msgColRef, {
      role: "assistant",
      content: aiResponse,
      timestamp: new Date().toISOString(),
    });

    // Atualiza metadados da conversa
    const { setDoc } = await import("firebase/firestore");
    await setDoc(
      convDocRef,
      {
        id: convId,
        lastMessage: message.slice(0, 100),
        updatedAt: serverTimestamp(),
        messageCount: prevMessages.length + 2,
      },
      { merge: true },
    );
  } catch (error) {
    console.error("[AI Chat] Erro ao salvar no Firestore:", error);
  }

  return { response: aiResponse, conversationId: convId };
}

// ─── Analise de imagem via Genkit Server Action ─────────────────────
export async function analyzeImageWithAI(
  imageFile: File,
  customPrompt?: string,
): Promise<string> {
  try {
    const { generateVisionResponse } = await import("@/app/actions/genkit-actions");

    // Converte imagem para base64
    const buffer = await imageFile.arrayBuffer();
    const base64 = btoa(
      new Uint8Array(buffer).reduce(
        (data, byte) => data + String.fromCharCode(byte),
        "",
      ),
    );

    const result = await generateVisionResponse(base64, imageFile.type || "image/jpeg", customPrompt);
    return result;
  } catch (error) {
    console.error("[AI Vision] Erro na analise:", error);
    throw new Error("Falha ao analisar imagem com IA. Tente novamente.");
  }
}

// ─── Leitura de conversas ────────────────────────────────────
export async function getConversations(): Promise<Conversation[]> {
  try {
    const q = query(conversationsRef, orderBy("updatedAt", "desc"), limit(50));
    const snapshot = await getDocs(q);

    return snapshot.docs.map((d) => {
      const data = d.data();
      return {
        id: d.id,
        lastMessage: data.lastMessage ?? "",
        updatedAt: data.updatedAt?.toDate?.()
          ? data.updatedAt.toDate().toISOString()
          : (data.updatedAt ?? ""),
        messageCount: data.messageCount ?? 0,
      };
    });
  } catch (error) {
    console.error("[AI Chat] Erro ao listar conversas:", error);
    return [];
  }
}

export async function getConversationMessages(
  conversationId: string,
  maxMessages = 50,
): Promise<ChatMessage[]> {
  try {
    const messagesRef = collection(
      db,
      "ai_conversations",
      conversationId,
      "messages",
    );
    const q = query(messagesRef, orderBy("timestamp"), limit(maxMessages));
    const snapshot = await getDocs(q);

    return snapshot.docs.map((d) => {
      const data = d.data();
      return {
        id: d.id,
        role: data.role ?? "user",
        content: data.content ?? "",
        timestamp: data.timestamp ?? "",
        imageUrl: data.imageUrl,
      };
    });
  } catch (error) {
    console.error("[AI Chat] Erro ao buscar mensagens:", error);
    return [];
  }
}

export async function deleteConversation(
  conversationId: string,
): Promise<void> {
  try {
    // Deleta mensagens
    const messagesRef = collection(
      db,
      "ai_conversations",
      conversationId,
      "messages",
    );
    const snapshot = await getDocs(messagesRef);
    const deletePromises = snapshot.docs.map((d) => deleteDoc(d.ref));
    await Promise.all(deletePromises);

    // Deleta conversa
    await deleteDoc(doc(db, "ai_conversations", conversationId));
  } catch (error) {
    console.error("[AI Chat] Erro ao deletar conversa:", error);
    throw error;
  }
}

// ─── Fallback (sem Gemini) ───────────────────────────────────
function getFallbackResponse(message: string): string {
  const msg = message.toLowerCase();

  if (["ferida", "ulcera", "lesao", "wound"].some((w) => msg.includes(w))) {
    return (
      "Para analise de feridas, recomendo fazer upload de uma foto. " +
      "O HEAL+ utiliza IA com modelos ResNet50, DermaIntel e BiomedCLIP " +
      "para classificar tecidos e sugerir condutas.\n\n" +
      "- Classificacao tecidual\n- Escalas PUSH, BWAT, Braden\n- Recomendacoes de curativo"
    );
  }
  if (["paciente", "historico", "buscar"].some((w) => msg.includes(w))) {
    return (
      "Para buscar pacientes, acesse a secao 'Pacientes' no menu. " +
      "La voce encontra historico completo, avaliacoes e relatorios de evolucao."
    );
  }
  if (["ola", "oi", "bom dia", "boa tarde", "boa noite"].some((w) => msg.includes(w))) {
    return (
      "Ola! Sou o assistente IA do HEAL+.\n\n" +
      "Posso ajudar com:\n" +
      "- Analise de imagens de feridas\n" +
      "- Dados de pacientes\n" +
      "- Relatorios clinicos\n" +
      "- Protocolos de estomaterapia\n\n" +
      "Como posso ajuda-lo?"
    );
  }

  return (
    "Como assistente HEAL+, posso ajudar com:\n\n" +
    "- **Analise de feridas** - upload de imagem para IA\n" +
    "- **Pacientes** - historico e dados clinicos\n" +
    "- **Relatorios** - geracao e exportacao\n" +
    "- **Protocolos** - condutas clinicas\n\n" +
    "Poderia ser mais especifico?"
  );
}
