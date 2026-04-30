const MOJIBAKE_PATTERN =
  /(?:\u00c3.|\u00c2.|\u00e2\u20ac|\ufffd)/;

function humanizeSlug(value: string) {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function repairMojibakeText(value: string) {
  if (!value || !MOJIBAKE_PATTERN.test(value)) {
    return value;
  }

  try {
    return decodeURIComponent(escape(value));
  } catch {
    return value;
  }
}

export function deepRepairMojibake<T>(value: T): T {
  if (typeof value === "string") {
    return repairMojibakeText(value) as T;
  }

  if (Array.isArray(value)) {
    return value.map((item) => deepRepairMojibake(item)) as T;
  }

  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, deepRepairMojibake(item)]),
    ) as T;
  }

  return value;
}

const MODEL_LABELS: Record<string, string> = {
  "heal-analyzer-headless-resnet": "HEAL+ ResNet Clínico com XAI",
  "heal-analyzer-headless-dl": "HEAL+ Deep Learning Clínico",
  "heal-analyzer-headless-ensemble": "HEAL+ Ensemble Clínico",
  "fallback-clinical-v1": "HEAL+ Clínico de Contingência",
};

export function presentHealAnalyzerModelName(modelVersion: string) {
  const repaired = repairMojibakeText(modelVersion);
  return MODEL_LABELS[repaired] || humanizeSlug(repaired || "modelo indisponivel");
}

export function presentHealAnalyzerModelDetails(modelVersion: string) {
  const repaired = repairMojibakeText(modelVersion);
  const label = presentHealAnalyzerModelName(repaired);
  return label === repaired ? label : `${label} (${repaired})`;
}
