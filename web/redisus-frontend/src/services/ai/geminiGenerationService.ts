import { auth } from '../../lib/firebase';

export const GEMINI_GENERATIVE_MODEL_LABEL = 'Gemini 2.0 Flash';

export interface GeminiGenerationRequest {
  message: string;
  conversationId?: string;
  context?: {
    patient_id?: string;
  };
}

export interface GeminiGenerationResult {
  text: string;
  source: string;
  modelName: string;
  conversationId?: string;
  timestamp?: string;
}

async function buildGeminiHeaders(): Promise<HeadersInit> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json'
  };

  const localMode = import.meta.env.VITE_HEAL_ANALYZER_LOCAL_MODE === 'true';
  if (localMode) return headers;

  const user = auth.currentUser;
  if (!user) {
    throw new Error('Usuario nao autenticado. Faca login para usar o Gemini.');
  }

  headers.Authorization = `Bearer ${await user.getIdToken()}`;
  return headers;
}

export async function generateWithGemini(request: GeminiGenerationRequest): Promise<GeminiGenerationResult> {
  const response = await fetch('/api/clinical/ai-chat', {
    method: 'POST',
    headers: await buildGeminiHeaders(),
    body: JSON.stringify({
      message: request.message,
      conversation_id: request.conversationId,
      context: request.context || {}
    })
  });

  const payload = await response.json().catch(() => null) as
    | {
        response?: string;
        source?: string;
        conversation_id?: string;
        timestamp?: string;
        detail?: string;
      }
    | null;

  if (!response.ok) {
    throw new Error(payload?.detail || `Gemini status ${response.status}`);
  }

  const text = payload?.response || '';
  if (!text.trim()) {
    throw new Error('Retorno vazio do Gemini.');
  }

  const source = payload?.source || 'gemini';
  return {
    text,
    source,
    modelName: source === 'gemini' ? GEMINI_GENERATIVE_MODEL_LABEL : 'Sistema de Regras (Fallback)',
    conversationId: payload?.conversation_id,
    timestamp: payload?.timestamp
  };
}
