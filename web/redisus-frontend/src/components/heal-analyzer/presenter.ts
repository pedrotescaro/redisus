import type {
  HealAnalyzerResult,
  HealAnalyzerTissueEntry,
} from "../../services/ai/heal-analyzer-service";
import {
  presentHealAnalyzerModelDetails,
  presentHealAnalyzerModelName,
  repairMojibakeText,
} from "../../lib/text-normalization";

export type WorkflowState =
  | "idle"
  | "marking"
  | "ready"
  | "loading"
  | "complete"
  | "error";
export type AnalyzerTabId = "original" | "segmentation" | "combined" | "attention";

type TissueBreakdown = {
  key: string;
  label: string;
  value: number;
  color: string;
  description: string;
  action: string;
};

const TISSUE_LABELS: Record<string, string> = {
  granulation: "Tecido de granulação",
  slough: "Esfacelo (fibrina)",
  necrosis: "Necrose de coagulação",
  epithelialization: "Epitelização",
};

const TISSUE_COLORS: Record<string, string> = {
  granulation: "#dc6b6b",
  slough: "#dfc547",
  necrosis: "#2f3640",
  epithelialization: "#76d6e3",
};

function normalizeText(value: string) {
  return repairMojibakeText(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

export function inferTissueKey(value: string) {
  const normalized = normalizeText(value);

  if (!normalized) return "tissue";
  if (
    normalized.includes("granulation") ||
    normalized.includes("granulacao")
  ) {
    return "granulation";
  }
  if (
    normalized.includes("slough") ||
    normalized.includes("esfacelo") ||
    normalized.includes("fibrin")
  ) {
    return "slough";
  }
  if (
    normalized.includes("necrosis") ||
    normalized.includes("necrose") ||
    normalized.includes("eschar") ||
    normalized.includes("escara")
  ) {
    return "necrosis";
  }
  if (
    normalized.includes("epithelial") ||
    normalized.includes("epitelizacao")
  ) {
    return "epithelialization";
  }
  return normalized.replace(/\s+/g, "_");
}

export function presentClinicalLabel(value: string) {
  const key = inferTissueKey(value);
  return TISSUE_LABELS[key] || repairMojibakeText(value) || "Sem classificação";
}

function normalizeTissueEntry(entry: HealAnalyzerTissueEntry): TissueBreakdown {
  const key = inferTissueKey(entry.name_en || entry.name);
  return {
    key,
    label:
      TISSUE_LABELS[key] ||
      repairMojibakeText(entry.name) ||
      repairMojibakeText(entry.name_en) ||
      "Tecido",
    value: Number(entry.percentage || 0),
    color: entry.color_hex || TISSUE_COLORS[key] || "#6b7280",
    description: repairMojibakeText(entry.description || ""),
    action: repairMojibakeText(entry.clinical_action || ""),
  };
}

export function getTissueBreakdown(
  analysis: HealAnalyzerResult | null,
): TissueBreakdown[] {
  if (!analysis) return [];

  if (analysis.tissues?.length) {
    return analysis.tissues
      .map(normalizeTissueEntry)
      .sort((left, right) => right.value - left.value);
  }

  return Object.entries(analysis.inference.tissue_percentages || {})
    .map(([key, value]) => ({
      key,
      label: TISSUE_LABELS[key] || presentClinicalLabel(key),
      value: Number(value || 0),
      color: TISSUE_COLORS[key] || "#6b7280",
      description: "",
      action: "",
    }))
    .sort((left, right) => right.value - left.value);
}

export function getSimpleExplanation(analysis: HealAnalyzerResult) {
  const justification =
    repairMojibakeText(analysis.primary_justification || "") ||
    repairMojibakeText(analysis.interpretation.summary || "") ||
    "A IA encontrou sinais visuais compativeis com o tecido destacado.";
  const caution = analysis.interpretation.requires_expert_review
    ? " Recomenda-se revisão profissional antes de qualquer decisão."
    : "";
  return `${justification}${caution}`;
}

export function getConfidencePercent(value: number) {
  return Math.max(0, Math.min(100, Math.round((value || 0) * 100)));
}

export function presentModelLabel(modelVersion: string) {
  return presentHealAnalyzerModelName(modelVersion);
}

export function presentModelDetails(modelVersion: string) {
  return presentHealAnalyzerModelDetails(modelVersion);
}

export function getRiskTone(riskLevel: string) {
  const normalized = normalizeText(riskLevel);
  if (normalized === "critico" || normalized === "urgent") {
    return "border-red-200 bg-red-50 text-red-700 dark:border-red-500/30 dark:bg-red-500/15 dark:text-red-300";
  }
  if (normalized === "alto" || normalized === "high") {
    return "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-300";
  }
  if (normalized === "moderado" || normalized === "moderate") {
    return "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/15 dark:text-sky-300";
  }
  return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-300";
}

export function getStatusCopy(
  state: WorkflowState,
  hasImage: boolean,
  hasConfirmedRoi = false,
) {
  if (state === "loading") {
    return {
      label: "Processando",
      caption: "A IA esta lendo a imagem e montando as visualizacoes.",
      tone: "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/15 dark:text-sky-300",
    };
  }

  if (state === "complete") {
    return {
      label: "Análise concluída",
      caption: "Resultado clínico pronto com explicação visual.",
      tone: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-300",
    };
  }

  if (state === "error") {
    return {
      label: "Falha na análise",
      caption: "Revise a imagem ou a conexão com a API clínica.",
      tone: "border-red-200 bg-red-50 text-red-700 dark:border-red-500/30 dark:bg-red-500/15 dark:text-red-300",
    };
  }

  if (state === "marking" || (hasImage && !hasConfirmedRoi)) {
    return {
      label: "Delimite a ferida",
      caption: "Confirme uma ou mais ROIs manuais para liberar a pipeline automatica.",
      tone: "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-300",
    };
  }

  if (hasConfirmedRoi) {
    return {
      label: "ROIs prontas",
      caption: "A análise já pode ser iniciada usando somente as áreas marcadas.",
      tone: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-300",
    };
  }

  if (hasImage) {
    return {
      label: "Imagem pronta",
      caption: "Você já pode seguir para a delimitação manual da ferida.",
      tone: "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-500/30 dark:bg-violet-500/15 dark:text-violet-300",
    };
  }

  return {
    label: "Aguardando imagem",
    caption: "Envie uma foto para liberar a leitura da IA.",
    tone: "border-outline-variant/30 bg-surface-container text-on-surface-variant dark:border-white/10 dark:bg-white/5 dark:text-slate-300",
  };
}
