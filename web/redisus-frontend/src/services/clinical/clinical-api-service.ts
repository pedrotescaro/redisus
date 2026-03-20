import { auth } from "@/lib/firebase";
import { waitForAuthenticatedUser } from "@/services/firebase/auth-service";

const API_BASE = process.env.NEXT_PUBLIC_CLINICAL_API_URL ?? "/api/clinical";

async function buildHeaders(extra?: HeadersInit): Promise<HeadersInit> {
  const user = auth.currentUser ?? (await waitForAuthenticatedUser());
  if (!user) {
    throw new Error("Usuario nao autenticado. Faca login para acessar a API clinica.");
  }

  const token = await user.getIdToken(true);
  if (!token) {
    throw new Error("Token Firebase indisponivel. Atualize a sessao e tente novamente.");
  }

  return {
    Authorization: `Bearer ${token}`,
    ...extra,
  };
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = await buildHeaders({
    "Content-Type": "application/json",
    ...(init?.headers ?? {}),
  });
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch (error) {
    const reason = error instanceof Error ? error.message : "falha de rede";
    throw new Error(
      `Não foi possível conectar ao backend clínico em ${API_BASE}. Verifique se a API está ativa. (${reason})`
    );
  }
  if (!response.ok) {
    throw new Error(`Erro API (${response.status})`);
  }
  return (await response.json()) as T;
}

export async function createEvaluation(payload: Record<string, unknown>) {
  return requestJson<{ id: string; case_id?: string }>("/evaluations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function uploadEvaluationImage(evaluationId: string, image: File, imageRole: string) {
  const formData = new FormData();
  formData.append("image", image);
  formData.append("imageRole", imageRole);
  const headers = await buildHeaders();
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/evaluations/${evaluationId}/images`, {
      method: "POST",
      headers,
      body: formData,
    });
  } catch (error) {
    const reason = error instanceof Error ? error.message : "falha de rede";
    throw new Error(
      `Não foi possível enviar imagens para ${API_BASE}. Verifique se a API está ativa. (${reason})`
    );
  }
  if (!response.ok) {
    throw new Error(`Falha upload imagem (${response.status})`);
  }
  return response.json();
}

export async function startEvaluationAnalysis(evaluationId: string) {
  return requestJson<{ jobId: string; status: string }>(`/evaluations/${evaluationId}/analyze`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function getAnalysisJob(jobId: string) {
  return requestJson<{ job: { status: string }; result?: unknown }>(`/analysis-jobs/${jobId}`);
}

export async function listPatientEvaluations(patientId: string, caseId?: string) {
  const qs = caseId ? `?caseId=${encodeURIComponent(caseId)}` : "";
  return requestJson<Array<Record<string, any>>>(`/patients/${patientId}/evaluations${qs}`);
}

export async function compareEvaluations(left: string, right: string) {
  const query = `?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`;
  return requestJson<{ left: any; right: any; deltas: any }>(`/comparisons${query}`);
}

export async function generateReport(payload: Record<string, unknown>) {
  return requestJson<{ reportId: string; report: any }>("/reports/generate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getReportDownloadUrl(reportId: string, format: "pdf" | "docx" | "json") {
  return `${API_BASE}/reports/${reportId}/download?format=${format}`;
}

export async function getClinicalApiHealth() {
  try {
    const response = await fetch(`${API_BASE}/health`);
    if (!response.ok) return { status: "down" as const };
    return (await response.json()) as { status: string; metrics?: Record<string, unknown> };
  } catch {
    return { status: "down" as const };
  }
}

