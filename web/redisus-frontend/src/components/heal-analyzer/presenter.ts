import type {
  HealAnalyzerResult,
  HealAnalyzerTissueEntry,
} from "@/services/ai/heal-analyzer-service";
import {
  presentHealAnalyzerModelDetails,
  presentHealAnalyzerModelName,
  repairMojibakeText,
} from "@/lib/text-normalization";

export type WorkflowState = "idle" | "ready" | "loading" | "complete" | "error";
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
    ? " Recomenda-se revisao profissional antes de qualquer decisao."
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
    return "bg-red-500/15 text-red-300 border-red-500/30";
  }
  if (normalized === "alto" || normalized === "high") {
    return "bg-amber-500/15 text-amber-300 border-amber-500/30";
  }
  if (normalized === "moderado" || normalized === "moderate") {
    return "bg-sky-500/15 text-sky-300 border-sky-500/30";
  }
  return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
}

export function getStatusCopy(state: WorkflowState, hasImage: boolean) {
  if (state === "loading") {
    return {
      label: "Processando",
      caption: "A IA esta lendo a imagem e montando as visualizacoes.",
      tone: "bg-sky-500/15 text-sky-300 border-sky-500/30",
    };
  }

  if (state === "complete") {
    return {
      label: "Analise concluida",
      caption: "Resultado clinico pronto com explicacao visual.",
      tone: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    };
  }

  if (state === "error") {
    return {
      label: "Falha na analise",
      caption: "Revise a imagem ou a conexao com a API clinica.",
      tone: "bg-red-500/15 text-red-300 border-red-500/30",
    };
  }

  if (hasImage) {
    return {
      label: "Imagem pronta",
      caption: "Voce ja pode iniciar a analise.",
      tone: "bg-violet-500/15 text-violet-300 border-violet-500/30",
    };
  }

  return {
    label: "Aguardando imagem",
    caption: "Envie uma foto para liberar a leitura da IA.",
    tone: "bg-white/5 text-slate-300 border-white/10",
  };
}
