import { onAuthStateChanged, type User } from "firebase/auth";

import { auth } from "../../lib/firebase";
import {
  toHealAnalyzerRoiRequestPayloads,
  type HealAnalyzerRoiSummary,
  toHealAnalyzerRoiRequestPayload,
  type HealAnalyzerRoiSelection,
} from "../../lib/heal-analyzer-roi";
import { deepRepairMojibake } from "../../lib/text-normalization";

const ANALYZER_API_BASE =
  import.meta.env.VITE_CLINICAL_API_URL ?? "/api/clinical";
const LOCAL_ANALYZER_MODE =
  import.meta.env.VITE_HEAL_ANALYZER_LOCAL_MODE === "true";

export type HealAnalyzerVisualAsset = {
  label: string;
  description: string;
  mime_type: string;
  data_url: string | null;
};

export type HealAnalyzerTissueEntry = {
  name: string;
  name_en: string;
  percentage: number;
  color_hex: string;
  description: string;
  clinical_action: string;
};

export type HealAnalyzerBorderAnalysis = {
  maceration: boolean;
  inflammation: boolean;
  regular_borders: boolean;
  description: string;
};

export type HealAnalyzerResult = {
  resource_type?: "wound_analysis";
  api_version?: string;
  status?: "completed";
  analysis_id: string;
  contract_version: string;
  model_version: string;
  generated_at: string;
  primary_tissue: string;
  primary_justification: string;
  processing_time_ms: number;
  is_valid_wound: boolean;
  rejection_reason: string;
  health_score: number;
  wound_area_px: number;
  tissues: HealAnalyzerTissueEntry[];
  border_analysis: HealAnalyzerBorderAnalysis | null;
  metadata: Record<string, unknown>;
  subject?: {
    patient_id: string | null;
    evaluation_id: string | null;
  };
  execution?: {
    engine: string;
    mode: "model_assisted" | "deterministic_fallback";
    degraded: boolean;
    processing_time_ms: number;
    components: Record<string, string>;
    warnings: string[];
  };
  safety?: {
    intended_use: string;
    decision_support_only: boolean;
    clinician_review_required: boolean;
    regulatory_status: string;
    limitations: string[];
  };
  tissue_analysis_trace?: {
    coverage_pct?: number;
    unclassified_pct?: number;
    final_tissue_percentages?: Record<string, number>;
    criteria?: string[];
  };
  wound_segmentation?: Record<string, unknown>;
  inference: {
    etiology: string;
    etiology_label: string;
    confidence: number;
    tissue_percentages: Record<string, number>;
    wound_area_cm2: number;
    fallback_used: boolean;
    needs_expert_review: boolean;
    confidence_level: string;
    confidence_entropy: number;
    confidence_margin: number;
  };
  interpretation: {
    summary: string;
    risk_level: string;
    priority: string;
    follow_up_days: number;
    requires_expert_review: boolean;
    recommendations: string[];
  };
  visuals?: {
    detection?: HealAnalyzerVisualAsset | null;
    segmentation?: HealAnalyzerVisualAsset | null;
    combined?: HealAnalyzerVisualAsset | null;
    attention?: HealAnalyzerVisualAsset | null;
  };
  roi?: HealAnalyzerRoiSummary | null;
  rois?: HealAnalyzerRoiSelection[] | null;
};

async function waitForAuthenticatedUser(timeoutMs = 5000) {
  if (auth.currentUser) {
    return auth.currentUser;
  }

  return new Promise<User | null>((resolve) => {
    let unsubscribe: () => void = () => {};
    const timer = window.setTimeout(() => {
      unsubscribe();
      resolve(null);
    }, timeoutMs);

    unsubscribe = onAuthStateChanged(auth, (user) => {
      if (!user) return;
      window.clearTimeout(timer);
      unsubscribe();
      resolve(user);
    });
  });
}

async function buildAuthorizedHeaders(): Promise<HeadersInit> {
  const localDevelopmentApi = import.meta.env.DEV && ANALYZER_API_BASE.startsWith("/");
  if (LOCAL_ANALYZER_MODE || localDevelopmentApi) {
    return {};
  }

  const user = auth.currentUser ?? (await waitForAuthenticatedUser());
  if (!user) {
    throw new Error("Usuário não autenticado. Faça login para analisar a imagem.");
  }

  const token = await user.getIdToken(true);
  if (!token) {
    throw new Error("Token do usuário indisponível. Atualize a sessão e tente novamente.");
  }

  return {
    Authorization: `Bearer ${token}`,
  };
}

export async function analyzeWithHealAnalyzer(
  image: File,
  options?: {
    patientId?: string;
    evaluationId?: string;
    roiSelection?: HealAnalyzerRoiSelection | null;
    roiSelections?: HealAnalyzerRoiSelection[] | null;
  },
): Promise<HealAnalyzerResult> {
  const formData = new FormData();
  formData.append("image", image);

  const patientId = options?.patientId?.trim();
  if (patientId) {
    formData.append("patient_id", patientId);
  }

  const evaluationId = options?.evaluationId?.trim();
  if (evaluationId) {
    formData.append("evaluation_id", evaluationId);
  }

  const roiSelections =
    options?.roiSelections?.filter(Boolean) ||
    (options?.roiSelection ? [options.roiSelection] : []);

  if (roiSelections.length === 1) {
    formData.append(
      "roi_payload",
      JSON.stringify(toHealAnalyzerRoiRequestPayload(roiSelections[0])),
    );
  } else if (roiSelections.length > 1) {
    formData.append(
      "roi_payload",
      JSON.stringify(toHealAnalyzerRoiRequestPayloads(roiSelections)),
    );
  }

  const headers = new Headers(await buildAuthorizedHeaders());
  headers.set("Idempotency-Key", `heal-analysis-${crypto.randomUUID()}`);

  let response: Response;
  try {
    response = await fetch(`${ANALYZER_API_BASE}/wound-analyses`, {
      method: "POST",
      headers,
      body: formData,
    });
  } catch (error) {
    const reason = error instanceof Error ? error.message : "falha de rede";
    throw new Error(
      `Não foi possível conectar ao HEAL analyzer em ${ANALYZER_API_BASE}. (${reason})`,
    );
  }

  const payload = (await response.json().catch(() => null)) as
    | HealAnalyzerResult
    | { detail?: string }
    | null;

  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? payload.detail
        : undefined;
    throw new Error(detail || `Falha ao executar a análise (${response.status}).`);
  }

  if (!payload || typeof payload !== "object" || !("analysis_id" in payload)) {
    throw new Error("Resposta inesperada do HEAL analyzer.");
  }

  return deepRepairMojibake(payload as HealAnalyzerResult);
}

