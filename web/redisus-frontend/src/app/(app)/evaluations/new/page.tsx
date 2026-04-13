"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type ReactNode,
} from "react";
import Image from "next/image";
import { onAuthStateChanged } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { listPatients } from "@/services/firebase/patient-service";
import type { NeuralAnalysisResult } from "@/services/ai/heal-ai-service";
import {
  createEvaluation,
  getAnalysisJob,
  startEvaluationAnalysis,
  uploadEvaluationImage,
} from "@/services/clinical/clinical-api-service";
import { syncEvaluationToFirebase } from "@/services/firebase/clinical-sync-service";
import {
  saveDraft as saveDraftToFirestore,
  loadDraft as loadDraftFromFirestore,
  deleteDraft as deleteDraftFromFirestore,
  addHistoryEntry,
} from "@/services/firebase/evaluation-draft-service";
import type { Patient } from "@/types/patient";

type PhotoSlot = {
  id: string;
  label: string;
  helper: string;
  file: File | null;
  preview: string | null;
};

type SectionId =
  | "patient"
  | "tissue"
  | "infection"
  | "moisture"
  | "edge"
  | "repair"
  | "social";

type PercentageField =
  | "granulationPct"
  | "epithelializationPct"
  | "sloughPct"
  | "dryNecrosisPct";

type ArrayField = "inflammationSigns" | "infectionSigns" | "periwoundSkin";

type BooleanField =
  | "culturePerformed"
  | "tunnelCavity"
  | "physicalActivity"
  | "alcoholUse"
  | "smoker";

type EvaluationForm = {
  woundWidth: string;
  woundLength: string;
  woundDepth: string;
  woundLocation: string;
  woundEtiology: string;
  woundEtiologyOther: string;
  evolutionTime: string;
  granulationPct: string;
  epithelializationPct: string;
  sloughPct: string;
  dryNecrosisPct: string;
  painScale: string;
  painFactors: string;
  inflammationSigns: string[];
  infectionSigns: string[];
  culturePerformed: boolean;
  cultureResult: string;
  exudateAmount: string;
  exudateType: string;
  exudateConsistency: string;
  edgeCharacteristics: string;
  edgeAttachment: string;
  healingSpeed: string;
  tunnelCavity: boolean;
  tunnelLocation: string;
  periwoundMoisture: string;
  periwoundExtension: string;
  periwoundSkin: string[];
  consultationTime: string;
  professionalName: string;
  professionalRegistry: string;
  followUpDate: string;
  notes: string;
  activityLevel: string;
  adherenceUnderstanding: string;
  socialSupport: string;
  physicalActivity: boolean;
  physicalActivityDescription: string;
  physicalActivityFrequency: string;
  alcoholUse: boolean;
  alcoholFrequency: string;
  smoker: boolean;
  nutritionalAssessment: string;
  waterIntake: string;
};

type SectionMeta = {
  id: SectionId;
  title: string;
  subtitle: string;
  icon: string;
  complete: boolean;
};

const PHOTO_SLOTS: PhotoSlot[] = [
  {
    id: "frontal",
    label: "Foto principal",
    helper: "Imagem principal da ferida",
    file: null,
    preview: null,
  },
  {
    id: "lateral",
    label: "Foto lateral",
    helper: "Vista complementar opcional",
    file: null,
    preview: null,
  },
  {
    id: "detail",
    label: "Foto detalhe",
    helper: "Macro ou area de interesse",
    file: null,
    preview: null,
  },
];

const LEGACY_PROTOCOLS = ["PUSH", "Braden", "BWAT"] as const;

const TISSUE_SEGMENTS: Array<{
  key: PercentageField;
  label: string;
  color: string;
}> = [
  { key: "granulationPct", label: "Granulacao", color: "#EF4444" },
  { key: "epithelializationPct", label: "Epitelizacao", color: "#EC4899" },
  { key: "sloughPct", label: "Esfacelo", color: "#F59E0B" },
  { key: "dryNecrosisPct", label: "Necrose seca", color: "#111827" },
];

const WOUND_LOCATION_OPTIONS = [
  "Regiao Sacral (Posterior)",
  "Calcanhar Direito",
  "Calcanhar Esquerdo",
  "Torax (Anterior)",
  "Costas (Posterior)",
  "Perna Esquerda (Anterior)",
  "Perna Direita (Anterior)",
  "Abdome",
  "MIE - Tornozelo",
  "MMII",
  "MMSS",
];

const ETIOLOGY_OPTIONS = [
  "Lesao por Pressao",
  "Ulcera Venosa",
  "Ulcera Arterial",
  "Pe Diabetico",
  "Ferida Cirurgica",
  "Ferida Traumatica",
  "Queimadura",
  "Outra",
];

const EXUDATE_AMOUNT_OPTIONS = [
  "Ausente",
  "Escasso",
  "Pequeno",
  "Moderado",
  "Abundante",
];

const EXUDATE_TYPE_OPTIONS = [
  "Seroso",
  "Sanguinolento",
  "Serossanguinolento",
  "Purulento",
  "Seropurulento",
];

const EXUDATE_CONSISTENCY_OPTIONS = ["Fina", "Viscosa", "Espessa"];

const EDGE_CHARACTERISTICS_OPTIONS = [
  "Regulares",
  "Irregulares",
  "Elevadas",
  "Maceradas",
  "Epitelizadas",
];

const EDGE_ATTACHMENT_OPTIONS = ["Aderidas", "Nao aderidas", "Descoladas"];

const HEALING_SPEED_OPTIONS = ["Rapida", "Moderada", "Lenta", "Estagnada"];

const PERIWOUND_MOISTURE_OPTIONS = ["Seca", "Hidratada", "Macerada", "Edemaciada"];

const ACTIVITY_LEVEL_OPTIONS = [
  "Acamado",
  "Sedentario",
  "Parcialmente ativo",
  "Ativo",
];

const ADHERENCE_OPTIONS = ["Boa", "Regular", "Baixa"];

const INFLAMMATION_SIGN_OPTIONS = [
  "Rubor",
  "Calor",
  "Edema",
  "Dor local",
  "Perda de funcao",
];

const INFECTION_SIGN_OPTIONS = [
  "Eritema perilesional",
  "Calor local",
  "Edema",
  "Dor local",
  "Exsudato purulento",
  "Odor fetido",
  "Retardo na cicatrizacao",
];

const PERIWOUND_SKIN_OPTIONS = [
  "Integra",
  "Eritematosa",
  "Macerada",
  "Seca/descamativa",
  "Eczematosa",
  "Hiperpigmentada",
  "Hipopigmentada",
  "Indurada",
  "Sensivel",
  "Edema",
];

const PAIN_LABELS = [
  "Sem dor",
  "Minima",
  "Leve",
  "Incomoda",
  "Moderada",
  "Desconforto",
  "Intensa",
  "Muito intensa",
  "Forte",
  "Insuportavel",
  "Maxima",
];

const SELECT_CLASS_NAME =
  "w-full rounded-2xl border border-outline-variant/15 bg-surface-container-high px-4 py-3 text-sm text-on-surface outline-none transition-all focus:border-primary focus:ring-2 focus:ring-primary/20";

const DEFAULT_FORM: EvaluationForm = {
  woundWidth: "",
  woundLength: "",
  woundDepth: "",
  woundLocation: "",
  woundEtiology: "",
  woundEtiologyOther: "",
  evolutionTime: "",
  granulationPct: "",
  epithelializationPct: "",
  sloughPct: "",
  dryNecrosisPct: "",
  painScale: "0",
  painFactors: "",
  inflammationSigns: [],
  infectionSigns: [],
  culturePerformed: false,
  cultureResult: "",
  exudateAmount: "",
  exudateType: "",
  exudateConsistency: "",
  edgeCharacteristics: "",
  edgeAttachment: "",
  healingSpeed: "",
  tunnelCavity: false,
  tunnelLocation: "",
  periwoundMoisture: "",
  periwoundExtension: "",
  periwoundSkin: [],
  consultationTime: "08:00",
  professionalName: "",
  professionalRegistry: "",
  followUpDate: "",
  notes: "",
  activityLevel: "",
  adherenceUnderstanding: "",
  socialSupport: "",
  physicalActivity: false,
  physicalActivityDescription: "",
  physicalActivityFrequency: "",
  alcoholUse: false,
  alcoholFrequency: "",
  smoker: false,
  nutritionalAssessment: "",
  waterIntake: "",
};

function parseInteger(value: string) {
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function clampPercentage(value: string) {
  return Math.max(0, Math.min(100, parseInteger(value)));
}

function parseDecimal(value: string) {
  const sanitized = value.replace(",", ".");
  const parsed = Number.parseFloat(sanitized);
  return Number.isFinite(parsed) ? parsed : 0;
}

function getPainColor(score: number) {
  if (score <= 2) return "#84CC16";
  if (score <= 4) return "#3B82F6";
  if (score <= 6) return "#FACC15";
  if (score <= 8) return "#F97316";
  return "#EF4444";
}

function resolveEtiology(form: EvaluationForm) {
  if (form.woundEtiology === "Outra") {
    return form.woundEtiologyOther.trim() || "Outra";
  }

  return form.woundEtiology.trim();
}

function normalizeLegacyEtiology(value: string) {
  const mapping: Record<string, string> = {
    pressure_ulcer: "Lesao por Pressao",
    diabetic_ulcer: "Pe Diabetico",
    venous_ulcer: "Ulcera Venosa",
    arterial_ulcer: "Ulcera Arterial",
    surgical_wound: "Ferida Cirurgica",
    traumatic_wound: "Ferida Traumatica",
    burn: "Queimadura",
    other: "Outra",
  };

  return mapping[value] ?? value;
}

function mergeDraftForm(
  value: unknown,
  legacyDraft?: Record<string, unknown>,
): EvaluationForm {
  const partial =
    value && typeof value === "object"
      ? (value as Partial<EvaluationForm>)
      : {};

  const timers =
    legacyDraft?.timersForm &&
    typeof legacyDraft.timersForm === "object" &&
    legacyDraft.timersForm !== null
      ? (legacyDraft.timersForm as Record<string, unknown>)
      : null;

  return {
    ...DEFAULT_FORM,
    ...partial,
    woundLocation:
      typeof partial.woundLocation === "string"
        ? partial.woundLocation
        : typeof legacyDraft?.woundLocation === "string"
          ? legacyDraft.woundLocation
          : DEFAULT_FORM.woundLocation,
    woundEtiology:
      typeof partial.woundEtiology === "string"
        ? partial.woundEtiology
        : typeof legacyDraft?.woundType === "string"
          ? normalizeLegacyEtiology(legacyDraft.woundType)
          : DEFAULT_FORM.woundEtiology,
    granulationPct:
      typeof partial.granulationPct === "string"
        ? partial.granulationPct
        : timers?.tGranulationPct !== undefined
          ? String(timers.tGranulationPct)
          : DEFAULT_FORM.granulationPct,
    epithelializationPct:
      typeof partial.epithelializationPct === "string"
        ? partial.epithelializationPct
        : timers?.tEpithelializationPct !== undefined
          ? String(timers.tEpithelializationPct)
          : DEFAULT_FORM.epithelializationPct,
    sloughPct:
      typeof partial.sloughPct === "string"
        ? partial.sloughPct
        : timers?.tSloughPct !== undefined
          ? String(timers.tSloughPct)
          : DEFAULT_FORM.sloughPct,
    dryNecrosisPct:
      typeof partial.dryNecrosisPct === "string"
        ? partial.dryNecrosisPct
        : timers?.tNecrosisPct !== undefined
          ? String(timers.tNecrosisPct)
          : DEFAULT_FORM.dryNecrosisPct,
    painScale:
      typeof partial.painScale === "string"
        ? partial.painScale
        : DEFAULT_FORM.painScale,
    inflammationSigns: Array.isArray(partial.inflammationSigns)
      ? partial.inflammationSigns.filter(
          (item): item is string => typeof item === "string",
        )
      : [],
    infectionSigns: Array.isArray(partial.infectionSigns)
      ? partial.infectionSigns.filter(
          (item): item is string => typeof item === "string",
        )
      : [],
    periwoundSkin: Array.isArray(partial.periwoundSkin)
      ? partial.periwoundSkin.filter(
          (item): item is string => typeof item === "string",
        )
      : [],
    culturePerformed: Boolean(partial.culturePerformed),
    tunnelCavity: Boolean(partial.tunnelCavity),
    physicalActivity: Boolean(partial.physicalActivity),
    alcoholUse: Boolean(partial.alcoholUse),
    smoker: Boolean(partial.smoker),
    consultationTime:
      typeof partial.consultationTime === "string" &&
      partial.consultationTime.trim()
        ? partial.consultationTime
        : DEFAULT_FORM.consultationTime,
  };
}

function calculateWoundArea(form: EvaluationForm) {
  const width = parseDecimal(form.woundWidth);
  const length = parseDecimal(form.woundLength);
  if (width <= 0 || length <= 0) return 0;
  return Number((width * length).toFixed(2));
}

function getDominantTissue(form: EvaluationForm) {
  const top = TISSUE_SEGMENTS.map((segment) => ({
    label: segment.label,
    value: clampPercentage(form[segment.key]),
  })).sort((left, right) => right.value - left.value)[0];

  if (!top || top.value <= 0) {
    return "Nao informado";
  }

  return `${top.label} (${top.value}%)`;
}

function buildClinicalDescription(form: EvaluationForm) {
  const details = [
    resolveEtiology(form) && `Etiologia: ${resolveEtiology(form)}`,
    form.evolutionTime.trim() &&
      `Tempo de evolucao: ${form.evolutionTime.trim()}`,
    `Dor: ${form.painScale}/10 (${PAIN_LABELS[clampPercentage(form.painScale)]})`,
    [form.exudateAmount, form.exudateType, form.exudateConsistency]
      .filter(Boolean)
      .length > 0 &&
      `Exsudato: ${[form.exudateAmount, form.exudateType, form.exudateConsistency]
        .filter(Boolean)
        .join(" / ")}`,
    [form.edgeCharacteristics, form.edgeAttachment]
      .filter(Boolean)
      .length > 0 &&
      `Bordas: ${[form.edgeCharacteristics, form.edgeAttachment]
        .filter(Boolean)
        .join(" / ")}`,
    form.notes.trim() && `Observacoes: ${form.notes.trim()}`,
  ].filter(Boolean);

  return details.join(" | ");
}

function getSummaryText(meta: SectionMeta) {
  return meta.complete ? "Completo" : "Preencher";
}

function SelectField({
  label,
  value,
  options,
  onChange,
  placeholder = "Selecione...",
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-on-surface-variant">{label}</label>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={SELECT_CLASS_NAME}
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
}

function ChipToggle({
  label,
  active,
  onClick,
  tone = "primary",
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  tone?: "primary" | "secondary" | "tertiary";
}) {
  const toneClass =
    tone === "secondary"
      ? active
        ? "bg-secondary/20 text-secondary border-secondary/20"
        : "bg-surface-container-high text-on-surface-variant border-outline-variant/10 hover:text-on-surface"
      : tone === "tertiary"
        ? active
          ? "bg-tertiary/20 text-tertiary border-tertiary/20"
          : "bg-surface-container-high text-on-surface-variant border-outline-variant/10 hover:text-on-surface"
        : active
          ? "bg-primary/20 text-primary border-primary/20"
          : "bg-surface-container-high text-on-surface-variant border-outline-variant/10 hover:text-on-surface";

  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-2 text-xs font-semibold transition-colors ${toneClass}`}
    >
      {label}
    </button>
  );
}

function ToggleCard({
  label,
  description,
  active,
  onClick,
}: {
  label: string;
  description?: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-start justify-between rounded-2xl border px-4 py-3 text-left transition-colors ${
        active
          ? "border-primary/25 bg-primary/10"
          : "border-outline-variant/10 bg-surface-container hover:bg-surface-container-high"
      }`}
    >
      <div>
        <p className="text-sm font-semibold text-on-surface">{label}</p>
        {description && (
          <p className="mt-1 text-xs text-on-surface-variant">{description}</p>
        )}
      </div>
      <span
        className={`material-symbols-outlined text-xl ${
          active ? "text-primary" : "text-on-surface-variant"
        }`}
      >
        {active ? "check_circle" : "radio_button_unchecked"}
      </span>
    </button>
  );
}

function AccordionSection({
  id,
  title,
  subtitle,
  icon,
  isOpen,
  onToggle,
  complete,
  children,
}: {
  id: SectionId;
  title: string;
  subtitle: string;
  icon: string;
  isOpen: boolean;
  onToggle: (id: SectionId) => void;
  complete: boolean;
  children: ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-3xl border border-outline-variant/8 bg-surface-container-low">
      <button
        type="button"
        onClick={() => onToggle(id)}
        className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left"
      >
        <div className="flex min-w-0 items-center gap-4">
          <div
            className={`flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-2xl ${
              complete
                ? "bg-primary/15 text-primary"
                : "bg-surface-container-high text-on-surface-variant"
            }`}
          >
            <span className="material-symbols-outlined">{icon}</span>
          </div>
          <div className="min-w-0">
            <p className="text-base font-bold text-on-surface">{title}</p>
            <p className="mt-1 text-sm text-on-surface-variant">{subtitle}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span
            className={`rounded-full px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] ${
              complete
                ? "bg-primary/12 text-primary"
                : "bg-surface-container-high text-on-surface-variant"
            }`}
          >
            {complete ? "Completo" : "Em aberto"}
          </span>
          <span className="material-symbols-outlined text-on-surface-variant">
            {isOpen ? "expand_less" : "expand_more"}
          </span>
        </div>
      </button>

      {isOpen && <div className="border-t border-outline-variant/8 px-6 py-6">{children}</div>}
    </section>
  );
}

export default function NewEvaluationPage() {
  const [uid, setUid] = useState<string | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loadingPatients, setLoadingPatients] = useState(true);
  const [patientSearch, setPatientSearch] = useState("");
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [evaluationDate, setEvaluationDate] = useState(
    new Date().toISOString().split("T")[0],
  );
  const [form, setForm] = useState<EvaluationForm>(DEFAULT_FORM);
  const [expandedSection, setExpandedSection] = useState<SectionId | null>("patient");
  const [savingDraft, setSavingDraft] = useState(false);
  const [savingEvaluation, setSavingEvaluation] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [aiAnalysis, setAiAnalysis] = useState<NeuralAnalysisResult | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [evaluationId, setEvaluationId] = useState<string | null>(null);
  const [photoSlots, setPhotoSlots] = useState<PhotoSlot[]>(PHOTO_SLOTS);

  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setUid(user?.uid ?? null);
    });

    return () => unsubscribe();
  }, []);

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const list = await listPatients();
        if (!active) return;
        setPatients(list);
      } finally {
        if (active) setLoadingPatients(false);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!uid) return;

    let active = true;

    void (async () => {
      try {
        const draft = await loadDraftFromFirestore(uid);
        if (!active || !draft) return;

        setPatientSearch((draft.patientSearch as string) ?? "");
        setSelectedPatientId((draft.selectedPatientId as string) ?? "");
        setEvaluationDate((draft.evaluationDate as string) ?? evaluationDate);
        setForm(mergeDraftForm(draft.form, draft));
        setStatusMessage("Rascunho restaurado automaticamente.");
      } catch {
        // ignore draft recovery failures
      }
    })();

    return () => {
      active = false;
    };
  }, [evaluationDate, uid]);

  const selectedPatient = useMemo(
    () => patients.find((patient) => patient.id === selectedPatientId) ?? null,
    [patients, selectedPatientId],
  );

  const filteredPatients = useMemo(() => {
    const normalized = patientSearch.trim().toLowerCase();
    if (!normalized) return patients;
    return patients.filter((patient) =>
      patient.name.toLowerCase().includes(normalized),
    );
  }, [patientSearch, patients]);

  const uploadedPhotos = useMemo(
    () => photoSlots.filter((slot) => slot.file).length,
    [photoSlots],
  );

  const tissueValues = useMemo(
    () =>
      TISSUE_SEGMENTS.map((segment) => ({
        ...segment,
        value: clampPercentage(form[segment.key]),
      })),
    [form],
  );

  const tissueTotal = useMemo(
    () => tissueValues.reduce((sum, segment) => sum + segment.value, 0),
    [tissueValues],
  );

  const tissueRemaining = Math.max(0, 100 - tissueTotal);
  const dominantTissue = getDominantTissue(form);
  const woundType = resolveEtiology(form);
  const woundAreaCm2 = calculateWoundArea(form);
  const painScore = clampPercentage(form.painScale);
  const clinicalDescription = buildClinicalDescription(form);
  const primaryPhoto = photoSlots[0];
  const secondaryPhotos = photoSlots.slice(1);

  const patientSectionReady = Boolean(selectedPatientId && evaluationDate);
  const tissueSectionReady = Boolean(
    uploadedPhotos > 0 &&
      form.woundLocation.trim() &&
      woundType &&
      tissueValues.some((segment) => segment.value > 0) &&
      tissueTotal <= 100,
  );
  const infectionSectionReady = Boolean(
    form.painFactors.trim() ||
      form.inflammationSigns.length > 0 ||
      form.infectionSigns.length > 0 ||
      form.culturePerformed,
  );
  const moistureSectionReady = Boolean(
    form.exudateAmount || form.exudateType || form.exudateConsistency,
  );
  const edgeSectionReady = Boolean(
    form.edgeCharacteristics ||
      form.edgeAttachment ||
      form.healingSpeed ||
      form.periwoundMoisture ||
      form.periwoundSkin.length > 0,
  );
  const repairSectionReady = Boolean(
    form.professionalName.trim() ||
      form.professionalRegistry.trim() ||
      form.followUpDate ||
      form.notes.trim(),
  );
  const socialSectionReady = Boolean(
    form.activityLevel ||
      form.adherenceUnderstanding ||
      form.socialSupport.trim() ||
      form.nutritionalAssessment.trim(),
  );

  const finalChecklistReady = Boolean(
    uid && patientSectionReady && tissueSectionReady && tissueTotal <= 100,
  );

  const sections: SectionMeta[] = [
    {
      id: "patient",
      title: "Dados pessoais",
      subtitle: "Paciente vinculado e contexto basico",
      icon: "person_outline",
      complete: patientSectionReady,
    },
    {
      id: "tissue",
      title: "T - Tecido",
      subtitle: "Fotos, medidas e leito da ferida",
      icon: "image",
      complete: tissueSectionReady,
    },
    {
      id: "infection",
      title: "I - Infeccao e inflamacao",
      subtitle: "Dor, sinais locais e cultura",
      icon: "medication",
      complete: infectionSectionReady,
    },
    {
      id: "moisture",
      title: "M - Umidade",
      subtitle: "Volume, tipo e consistencia do exsudato",
      icon: "water_drop",
      complete: moistureSectionReady,
    },
    {
      id: "edge",
      title: "E - Bordas",
      subtitle: "Bordas, tunel/cavidade e pele perilesional",
      icon: "scan",
      complete: edgeSectionReady,
    },
    {
      id: "repair",
      title: "R - Registro e retorno",
      subtitle: "Profissional, horario, observacoes e retorno",
      icon: "edit_note",
      complete: repairSectionReady,
    },
    {
      id: "social",
      title: "S - Fatores sociais",
      subtitle: "Atividade, adesao e contexto social",
      icon: "diversity_3",
      complete: socialSectionReady,
    },
  ];

  const updateFormField = <K extends keyof EvaluationForm>(
    key: K,
    value: EvaluationForm[K],
  ) => {
    setForm((current) => ({
      ...current,
      [key]: value,
    }));
  };

  const toggleBooleanField = (key: BooleanField) => {
    setForm((current) => ({
      ...current,
      [key]: !current[key],
    }));
  };

  const toggleArrayValue = (field: ArrayField, option: string) => {
    setForm((current) => {
      const currentValues = current[field];
      const exists = currentValues.includes(option);

      return {
        ...current,
        [field]: exists
          ? currentValues.filter((value) => value !== option)
          : [...currentValues, option],
      };
    });
  };

  const handleTissuePercentageChange = (field: PercentageField, rawValue: string) => {
    const relatedFields: PercentageField[] = [
      "granulationPct",
      "epithelializationPct",
      "sloughPct",
      "dryNecrosisPct",
    ];

    if (rawValue === "") {
      setForm((current) => ({
        ...current,
        [field]: "",
      }));
      return;
    }

    const nextValue = clampPercentage(rawValue);

    if (nextValue === 100) {
      setForm((current) => {
        const nextForm = { ...current };
        relatedFields.forEach((item) => {
          nextForm[item] = item === field ? "100" : "";
        });
        return nextForm;
      });
      return;
    }

    setForm((current) => {
      const nextForm = { ...current, [field]: String(nextValue) };
      const otherFields = relatedFields.filter((item) => item !== field);
      const currentOthers = otherFields.reduce(
        (sum, item) => sum + clampPercentage(nextForm[item]),
        0,
      );

      if (nextValue + currentOthers > 100) {
        let overflow = nextValue + currentOthers - 100;

        for (const item of otherFields) {
          const currentValue = clampPercentage(nextForm[item]);
          if (currentValue <= 0) continue;

          if (currentValue >= overflow) {
            const adjusted = currentValue - overflow;
            nextForm[item] = adjusted > 0 ? String(adjusted) : "";
            break;
          }

          overflow -= currentValue;
          nextForm[item] = "";
        }
      }

      return nextForm;
    });
  };

  const handlePhotoUpload = (slotId: string, file: File) => {
    const reader = new FileReader();

    reader.onload = (event) => {
      setPhotoSlots((current) =>
        current.map((slot) =>
          slot.id === slotId
            ? { ...slot, file, preview: event.target?.result as string }
            : slot,
        ),
      );
    };

    reader.readAsDataURL(file);
  };

  const handleFileInputChange = (
    slotId: string,
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;
    handlePhotoUpload(slotId, file);
    event.target.value = "";
  };

  const removePhoto = (slotId: string) => {
    setPhotoSlots((current) =>
      current.map((slot) =>
        slot.id === slotId ? { ...slot, file: null, preview: null } : slot,
      ),
    );
  };

  const handleSectionToggle = (id: SectionId) => {
    setExpandedSection((current) => (current === id ? null : id));
  };

  const saveDraft = async () => {
    if (!uid) {
      setStatusMessage("Faca login para salvar rascunhos.");
      return;
    }

    setSavingDraft(true);
    setStatusMessage(null);

    try {
      await saveDraftToFirestore(uid, {
        patientSearch,
        selectedPatientId,
        evaluationDate,
        form,
        legacyProtocolsDisabled: LEGACY_PROTOCOLS,
      });

      setStatusMessage("Rascunho salvo com sucesso.");
    } catch {
      setStatusMessage("Falha ao salvar rascunho.");
    } finally {
      setSavingDraft(false);
    }
  };

  const finalizeEvaluation = async () => {
    if (!finalChecklistReady || !uid) {
      setStatusMessage(
        "Selecione o paciente, adicione foto, informe localizacao/etiologia e preencha o leito da ferida para finalizar.",
      );
      return;
    }

    setSavingEvaluation(true);
    setStatusMessage(null);

    const payload = {
      patient_id: selectedPatientId,
      evaluation_date: evaluationDate,
      professional_name: form.professionalName.trim() || "Equipe HEAL+",
      wound_type: woundType,
      wound_location: form.woundLocation.trim(),
      clinical_description: clinicalDescription,
      push_score: 0,
      braden_score: 0,
      bwat_score: 0,
      pain_score: painScore,
      wound_area_cm2: woundAreaCm2,
      tissue_composition: {
        granulation: clampPercentage(form.granulationPct),
        slough: clampPercentage(form.sloughPct),
        necrosis: clampPercentage(form.dryNecrosisPct),
        epithelialization: clampPercentage(form.epithelializationPct),
      },
      timers_payload: {
        ...form,
        uploadedPhotoRoles: photoSlots
          .filter((slot) => slot.file)
          .map((slot) => slot.id),
        tissueTotalPct: tissueTotal,
        dominantTissue,
        legacyProtocolsDisabled: LEGACY_PROTOCOLS,
      },
    };

    try {
      const created = await createEvaluation(payload);
      setEvaluationId(created.id);

      const uploadPromises = photoSlots
        .filter((slot) => slot.file)
        .map((slot) =>
          uploadEvaluationImage(created.id, slot.file as File, slot.id),
        );
      await Promise.all(uploadPromises);

      await syncEvaluationToFirebase({
        apiEvaluationId: created.id,
        patientId: selectedPatientId,
        patientName: selectedPatient?.name ?? "Paciente",
        evaluationDate,
        woundType,
        woundLocation: form.woundLocation.trim(),
        clinicalDescription,
        pushScore: 0,
        bradenScore: 0,
        bwatScore: 0,
        photoCount: uploadedPhotos,
        timersPayload: payload.timers_payload as Record<string, unknown>,
      });

      await addHistoryEntry(uid, {
        apiEvaluationId: created.id,
        patientId: selectedPatientId,
        patientName: selectedPatient?.name ?? "Paciente",
        evaluationDate,
        woundType,
        woundLocation: form.woundLocation.trim(),
        clinicalDescription,
        painScore,
        woundAreaCm2,
        timersPayload: payload.timers_payload,
      });

      await deleteDraftFromFirestore(uid);
      setStatusMessage(
        "Avaliacao finalizada com TIMERS do mobile e sincronizada no backend/Firebase.",
      );
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Falha ao finalizar avaliacao no backend.";
      setStatusMessage(message);
    } finally {
      setSavingEvaluation(false);
    }
  };

  const runAiAnalysis = async () => {
    if (!evaluationId) {
      setAiError(
        "Finalize a avaliacao primeiro para gerar o ID clinico e liberar a analise por IA.",
      );
      return;
    }

    if (!photoSlots.some((slot) => slot.file)) {
      setAiError("Adicione ao menos uma foto para executar a IA.");
      return;
    }

    setAiLoading(true);
    setAiError(null);
    setAiAnalysis(null);

    try {
      const job = await startEvaluationAnalysis(evaluationId);
      let attempts = 0;

      while (attempts < 20) {
        // eslint-disable-next-line no-await-in-loop
        await new Promise((resolve) => setTimeout(resolve, 1200));
        // eslint-disable-next-line no-await-in-loop
        const current = await getAnalysisJob(job.jobId);

        if (current.job.status === "completed" && current.result) {
          const result = current.result as {
            etiology: string;
            confidence: number;
            tissue_percentages?: {
              granulation?: number;
              slough?: number;
              necrosis?: number;
            };
            recommendations?: string[];
          };

          setAiAnalysis({
            woundType: result.etiology,
            confidence: result.confidence ?? 0,
            tissueComposition: {
              granulation: result.tissue_percentages?.granulation ?? 0,
              slough: result.tissue_percentages?.slough ?? 0,
              necrosis: result.tissue_percentages?.necrosis ?? 0,
            },
            riskLevel: "moderate",
            recommendations: result.recommendations ?? [],
          });
          return;
        }

        if (current.job.status === "failed") {
          throw new Error("Job de IA falhou.");
        }

        attempts += 1;
      }

      throw new Error("Tempo limite de processamento da IA excedido.");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Falha ao executar a IA.";
      setAiError(message);
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-3xl font-extrabold font-headline text-on-surface">
            Nova avaliacao
          </h1>
          <p className="mt-2 max-w-3xl text-sm text-on-surface-variant">
            Fluxo web ajustado para seguir o formulario TIMERS do mobile. Os
            protocolos legados foram comentados e a avaliacao do leito agora usa
            a mesma barra colorida com porcentagens.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {LEGACY_PROTOCOLS.map((protocol) => (
            <span
              key={protocol}
              className="rounded-full bg-tertiary/12 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-tertiary"
            >
              {protocol} comentado
            </span>
          ))}
          <span className="rounded-full bg-primary/12 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-primary">
            TIMERS mobile ativo
          </span>
        </div>
      </div>

      <div className="grid gap-8 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="space-y-4 xl:sticky xl:top-24 xl:self-start">
          <div className="rounded-3xl border border-outline-variant/8 bg-surface-container-low p-6">
            <p className="text-xs font-bold uppercase tracking-[0.22em] text-on-surface-variant">
              Navegacao
            </p>
            <div className="mt-4 space-y-2">
              {sections.map((section) => (
                <button
                  key={section.id}
                  type="button"
                  onClick={() => setExpandedSection(section.id)}
                  className={`flex w-full items-center justify-between rounded-2xl px-4 py-3 text-left transition-colors ${
                    expandedSection === section.id
                      ? "bg-primary/10 text-primary"
                      : "bg-surface-container text-on-surface hover:bg-surface-container-high"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className="material-symbols-outlined text-lg">
                      {section.icon}
                    </span>
                    <div>
                      <p className="text-sm font-semibold">{section.title}</p>
                      <p className="text-[11px] uppercase tracking-[0.16em] text-on-surface-variant">
                        {getSummaryText(section)}
                      </p>
                    </div>
                  </div>
                  <span
                    className={`h-2.5 w-2.5 rounded-full ${
                      section.complete ? "bg-primary" : "bg-outline-variant/25"
                    }`}
                  />
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border border-outline-variant/8 bg-surface-container-low p-6">
            <p className="text-xs font-bold uppercase tracking-[0.22em] text-on-surface-variant">
              Checklist
            </p>
            <div className="mt-4 space-y-3 text-sm">
              <p className={patientSectionReady ? "text-primary" : "text-error"}>
                • Paciente selecionado e data da avaliacao definida
              </p>
              <p className={uploadedPhotos > 0 ? "text-primary" : "text-error"}>
                • Pelo menos uma foto da ferida anexada
              </p>
              <p
                className={
                  form.woundLocation.trim() && woundType ? "text-primary" : "text-error"
                }
              >
                • Localizacao e etiologia preenchidas
              </p>
              <p
                className={
                  tissueValues.some((segment) => segment.value > 0)
                    ? "text-primary"
                    : "text-error"
                }
              >
                • Percentuais do leito informados
              </p>
              <p className={tissueTotal <= 100 ? "text-primary" : "text-error"}>
                • Soma do leito ate 100% (atual: {tissueTotal}%)
              </p>
            </div>
          </div>

          <div className="rounded-3xl border border-outline-variant/8 bg-surface-container-low p-6">
            <p className="text-xs font-bold uppercase tracking-[0.22em] text-on-surface-variant">
              Resumo rapido
            </p>
            <div className="mt-4 space-y-3 text-sm text-on-surface-variant">
              <p>
                <span className="font-semibold text-on-surface">Paciente:</span>{" "}
                {selectedPatient?.name ?? "Nao selecionado"}
              </p>
              <p>
                <span className="font-semibold text-on-surface">Etiologia:</span>{" "}
                {woundType || "Nao informada"}
              </p>
              <p>
                <span className="font-semibold text-on-surface">Leito dominante:</span>{" "}
                {dominantTissue}
              </p>
              <p>
                <span className="font-semibold text-on-surface">Area estimada:</span>{" "}
                {woundAreaCm2 > 0 ? `${woundAreaCm2} cm2` : "Nao calculada"}
              </p>
            </div>
          </div>
        </aside>

        <div className="space-y-5">
          <AccordionSection
            id="patient"
            title="Dados pessoais"
            subtitle="Vinculo com o paciente e dados basicos do cadastro"
            icon="person_outline"
            isOpen={expandedSection === "patient"}
            onToggle={handleSectionToggle}
            complete={patientSectionReady}
          >
            <div className="grid gap-6">
              <div className="space-y-2">
                <label className="text-sm font-medium text-on-surface-variant">
                  Buscar paciente
                </label>
                <div className="relative">
                  <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant">
                    search
                  </span>
                  <Input
                    value={patientSearch}
                    onChange={(event) => setPatientSearch(event.target.value)}
                    placeholder="Pesquisar por nome..."
                    className="pl-11"
                  />
                </div>
              </div>

              <div className="rounded-3xl border border-outline-variant/8 bg-surface-container p-3">
                {loadingPatients ? (
                  <p className="px-2 py-4 text-sm text-on-surface-variant">
                    Carregando pacientes...
                  </p>
                ) : filteredPatients.length === 0 ? (
                  <p className="px-2 py-4 text-sm text-on-surface-variant">
                    Nenhum paciente encontrado.
                  </p>
                ) : (
                  <div className="grid gap-2 md:grid-cols-2">
                    {filteredPatients.slice(0, 8).map((patient) => (
                      <button
                        type="button"
                        key={patient.id}
                        onClick={() => setSelectedPatientId(patient.id)}
                        className={`rounded-2xl border px-4 py-3 text-left transition-colors ${
                          selectedPatientId === patient.id
                            ? "border-primary/20 bg-primary/10"
                            : "border-outline-variant/8 bg-surface-container-high hover:bg-surface-container"
                        }`}
                      >
                        <p className="text-sm font-semibold text-on-surface">
                          {patient.name}
                        </p>
                        <p className="mt-1 text-xs text-on-surface-variant">
                          {patient.phone || "Sem telefone"} |{" "}
                          {patient.email || "Sem e-mail"}
                        </p>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Data da avaliacao
                  </label>
                  <Input
                    type="date"
                    value={evaluationDate}
                    onChange={(event) => setEvaluationDate(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Hora da consulta
                  </label>
                  <Input
                    type="time"
                    value={form.consultationTime}
                    onChange={(event) =>
                      updateFormField("consultationTime", event.target.value)
                    }
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Nome completo
                  </label>
                  <Input
                    value={selectedPatient?.name ?? ""}
                    readOnly
                    placeholder="Selecione um paciente"
                    className="bg-surface-container-high/70"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Data de nascimento
                  </label>
                  <Input
                    value={selectedPatient?.birthDate ?? ""}
                    readOnly
                    className="bg-surface-container-high/70"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Telefone
                  </label>
                  <Input
                    value={selectedPatient?.phone ?? ""}
                    readOnly
                    className="bg-surface-container-high/70"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Email
                  </label>
                  <Input
                    value={selectedPatient?.email ?? ""}
                    readOnly
                    className="bg-surface-container-high/70"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Profissao
                  </label>
                  <Input
                    value={selectedPatient?.profession ?? ""}
                    readOnly
                    className="bg-surface-container-high/70"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Estado civil
                  </label>
                  <Input
                    value={selectedPatient?.maritalStatus ?? ""}
                    readOnly
                    className="bg-surface-container-high/70"
                  />
                </div>
              </div>
            </div>
          </AccordionSection>
          <AccordionSection
            id="tissue"
            title="T - Tecido"
            subtitle="Fotos, medidas, etiologia e avaliacao do leito da ferida"
            icon="image"
            isOpen={expandedSection === "tissue"}
            onToggle={handleSectionToggle}
            complete={tissueSectionReady}
          >
            <div className="space-y-6">
              <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
                <div className="rounded-3xl border border-outline-variant/8 bg-surface-container p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-on-surface">
                        Foto principal
                      </p>
                      <p className="text-xs text-on-surface-variant">
                        Imagem principal da ferida como no fluxo mobile
                      </p>
                    </div>
                    <span className="rounded-full bg-primary/12 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-primary">
                      {uploadedPhotos}/3 anexadas
                    </span>
                  </div>

                  <input
                    id={`photo-${primaryPhoto.id}`}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(event) => handleFileInputChange(primaryPhoto.id, event)}
                  />

                  <label
                    htmlFor={`photo-${primaryPhoto.id}`}
                    className="relative mt-4 flex min-h-[280px] cursor-pointer items-center justify-center overflow-hidden rounded-3xl border border-dashed border-outline-variant/15 bg-surface-container-high"
                  >
                    {primaryPhoto.preview ? (
                      <Image
                        src={primaryPhoto.preview}
                        alt={primaryPhoto.label}
                        fill
                        unoptimized
                        className="object-cover"
                      />
                    ) : (
                      <div className="flex max-w-sm flex-col items-center px-6 text-center">
                        <span className="material-symbols-outlined text-5xl text-primary">
                          add_a_photo
                        </span>
                        <p className="mt-3 text-base font-semibold text-on-surface">
                          Adicionar foto da ferida
                        </p>
                        <p className="mt-2 text-sm text-on-surface-variant">
                          Toque para tirar foto ou escolher da galeria, igual ao
                          preenchimento do mobile.
                        </p>
                      </div>
                    )}
                  </label>

                  <div className="mt-4 flex flex-wrap gap-3">
                    <label
                      htmlFor={`photo-${primaryPhoto.id}`}
                      className="inline-flex cursor-pointer items-center rounded-2xl bg-primary px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90"
                    >
                      {primaryPhoto.preview ? "Trocar foto" : "Selecionar foto"}
                    </label>
                    {primaryPhoto.preview && (
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => removePhoto(primaryPhoto.id)}
                      >
                        Remover
                      </Button>
                    )}
                  </div>
                </div>

                <div className="grid gap-4">
                  {secondaryPhotos.map((slot) => (
                    <div
                      key={slot.id}
                      className="rounded-3xl border border-outline-variant/8 bg-surface-container p-4"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-on-surface">
                            {slot.label}
                          </p>
                          <p className="text-xs text-on-surface-variant">
                            {slot.helper}
                          </p>
                        </div>
                        <span className="material-symbols-outlined text-on-surface-variant">
                          photo_camera
                        </span>
                      </div>

                      <input
                        id={`photo-${slot.id}`}
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={(event) => handleFileInputChange(slot.id, event)}
                      />

                      <label
                        htmlFor={`photo-${slot.id}`}
                        className="relative mt-4 flex min-h-[160px] cursor-pointer items-center justify-center overflow-hidden rounded-2xl border border-dashed border-outline-variant/15 bg-surface-container-high"
                      >
                        {slot.preview ? (
                          <Image
                            src={slot.preview}
                            alt={slot.label}
                            fill
                            unoptimized
                            className="object-cover"
                          />
                        ) : (
                          <div className="px-4 text-center">
                            <span className="material-symbols-outlined text-3xl text-primary">
                              imagesmode
                            </span>
                            <p className="mt-2 text-sm font-medium text-on-surface">
                              Adicionar imagem
                            </p>
                          </div>
                        )}
                      </label>

                      <div className="mt-3 flex flex-wrap gap-2">
                        <label
                          htmlFor={`photo-${slot.id}`}
                          className="inline-flex cursor-pointer items-center rounded-2xl border border-outline-variant/12 bg-surface-container-high px-4 py-2 text-sm font-medium text-on-surface transition-colors hover:bg-surface-container"
                        >
                          {slot.preview ? "Trocar" : "Selecionar"}
                        </label>
                        {slot.preview && (
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => removePhoto(slot.id)}
                          >
                            Remover
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Largura (cm)
                  </label>
                  <Input
                    value={form.woundWidth}
                    onChange={(event) =>
                      updateFormField("woundWidth", event.target.value)
                    }
                    placeholder="Ex.: 4,5"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Comprimento (cm)
                  </label>
                  <Input
                    value={form.woundLength}
                    onChange={(event) =>
                      updateFormField("woundLength", event.target.value)
                    }
                    placeholder="Ex.: 6,2"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Profundidade (cm)
                  </label>
                  <Input
                    value={form.woundDepth}
                    onChange={(event) =>
                      updateFormField("woundDepth", event.target.value)
                    }
                    placeholder="Ex.: 1,0"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Tempo de evolucao
                  </label>
                  <Input
                    value={form.evolutionTime}
                    onChange={(event) =>
                      updateFormField("evolutionTime", event.target.value)
                    }
                    placeholder="Ex.: 3 semanas"
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,0.75fr)]">
                <SelectField
                  label="Localizacao"
                  value={form.woundLocation}
                  options={WOUND_LOCATION_OPTIONS}
                  onChange={(value) => updateFormField("woundLocation", value)}
                />
                <SelectField
                  label="Etiologia"
                  value={form.woundEtiology}
                  options={ETIOLOGY_OPTIONS}
                  onChange={(value) => updateFormField("woundEtiology", value)}
                />
                <div className="rounded-3xl border border-outline-variant/8 bg-surface-container p-4">
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-on-surface-variant">
                    Resumo
                  </p>
                  <div className="mt-3 space-y-2 text-sm text-on-surface-variant">
                    <p>
                      <span className="font-semibold text-on-surface">Area:</span>{" "}
                      {woundAreaCm2 > 0 ? `${woundAreaCm2} cm2` : "Nao calculada"}
                    </p>
                    <p>
                      <span className="font-semibold text-on-surface">
                        Leito dominante:
                      </span>{" "}
                      {dominantTissue}
                    </p>
                  </div>
                </div>
              </div>

              {form.woundEtiology === "Outra" && (
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Especifique a etiologia
                  </label>
                  <Input
                    value={form.woundEtiologyOther}
                    onChange={(event) =>
                      updateFormField("woundEtiologyOther", event.target.value)
                    }
                    placeholder="Detalhe a etiologia"
                  />
                </div>
              )}

              <div className="rounded-3xl border border-outline-variant/8 bg-surface-container p-5">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <p className="text-base font-bold text-on-surface">
                      Avaliacao do leito da ferida
                    </p>
                    <p className="mt-1 text-sm text-on-surface-variant">
                      Soma maxima de 100%, com barra e cores como no mobile.
                    </p>
                  </div>
                  <span
                    className={`rounded-full px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] ${
                      tissueTotal <= 100
                        ? "bg-primary/12 text-primary"
                        : "bg-error/12 text-error"
                    }`}
                  >
                    Total {tissueTotal}%
                  </span>
                </div>

                <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  {tissueValues.map((segment) => (
                    <div
                      key={segment.key}
                      className="rounded-2xl border border-outline-variant/8 bg-surface-container-high p-4"
                    >
                      <label className="text-sm font-semibold text-on-surface">
                        {segment.label}
                      </label>
                      <Input
                        type="number"
                        min="0"
                        max="100"
                        value={form[segment.key]}
                        onChange={(event) =>
                          handleTissuePercentageChange(segment.key, event.target.value)
                        }
                        placeholder="0"
                        className="mt-3"
                      />
                      <div className="mt-3 flex items-center justify-between">
                        <div
                          className="h-3 w-3 rounded-full"
                          style={{ backgroundColor: segment.color }}
                        />
                        <span className="text-xs font-semibold text-on-surface-variant">
                          {segment.value}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-5 overflow-hidden rounded-full border border-outline-variant/10 bg-surface-container-high">
                  <div className="flex h-5 w-full">
                    {tissueValues.map((segment) =>
                      segment.value > 0 ? (
                        <div
                          key={segment.key}
                          className="h-full"
                          style={{
                            width: `${segment.value}%`,
                            backgroundColor: segment.color,
                          }}
                        />
                      ) : null,
                    )}
                    {tissueRemaining > 0 && (
                      <div
                        className="h-full bg-outline-variant/15"
                        style={{ width: `${tissueRemaining}%` }}
                      />
                    )}
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-3">
                  {tissueValues.map((segment) => (
                    <div
                      key={segment.key}
                      className="inline-flex items-center gap-2 rounded-full bg-surface-container-high px-3 py-2 text-xs font-semibold text-on-surface"
                    >
                      <span
                        className="h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: segment.color }}
                      />
                      {segment.label}: {segment.value}%
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </AccordionSection>

          <AccordionSection
            id="infection"
            title="I - Infeccao e inflamacao"
            subtitle="Dor, sinais locais, cultura e aspectos clinicos"
            icon="medication"
            isOpen={expandedSection === "infection"}
            onToggle={handleSectionToggle}
            complete={infectionSectionReady}
          >
            <div className="space-y-6">
              <div className="rounded-3xl border border-outline-variant/8 bg-surface-container p-5">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <p className="text-base font-bold text-on-surface">
                      Intensidade da dor
                    </p>
                    <p className="mt-1 text-sm text-on-surface-variant">
                      Escala de 0 a 10 como no formulario mobile.
                    </p>
                  </div>
                  <div
                    className="rounded-2xl px-4 py-2 text-sm font-bold"
                    style={{
                      backgroundColor: getPainColor(painScore),
                      color: "#FFFFFF",
                    }}
                  >
                    {painScore}/10 • {PAIN_LABELS[painScore]}
                  </div>
                </div>

                <div className="mt-5 grid grid-cols-11 overflow-hidden rounded-2xl border border-outline-variant/10">
                  {Array.from({ length: 11 }, (_, value) => {
                    const active = painScore === value;
                    return (
                      <button
                        key={value}
                        type="button"
                        onClick={() => updateFormField("painScale", String(value))}
                        className={`px-2 py-3 text-sm font-semibold transition-colors ${
                          active
                            ? "text-white"
                            : "border-r border-outline-variant/10 bg-surface-container-high text-on-surface-variant hover:text-on-surface"
                        }`}
                        style={
                          active
                            ? { backgroundColor: getPainColor(value) }
                            : undefined
                        }
                      >
                        {value}
                      </button>
                    );
                  })}
                </div>

                <div className="mt-2 flex items-center justify-between text-xs text-on-surface-variant">
                  <span>Sem dor</span>
                  <span>Maxima</span>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-on-surface-variant">
                  Fatores que aliviam ou pioram a dor
                </label>
                <Textarea
                  rows={3}
                  value={form.painFactors}
                  onChange={(event) =>
                    updateFormField("painFactors", event.target.value)
                  }
                  placeholder="Descreva fatores associados a dor"
                />
              </div>

              <div className="grid gap-5 lg:grid-cols-2">
                <div className="rounded-3xl border border-outline-variant/8 bg-surface-container p-5">
                  <p className="text-sm font-semibold text-on-surface">
                    Sinais de inflamacao
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {INFLAMMATION_SIGN_OPTIONS.map((option) => (
                      <ChipToggle
                        key={option}
                        label={option}
                        tone="secondary"
                        active={form.inflammationSigns.includes(option)}
                        onClick={() => toggleArrayValue("inflammationSigns", option)}
                      />
                    ))}
                  </div>
                </div>

                <div className="rounded-3xl border border-outline-variant/8 bg-surface-container p-5">
                  <p className="text-sm font-semibold text-on-surface">
                    Sinais de infeccao local
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {INFECTION_SIGN_OPTIONS.map((option) => (
                      <ChipToggle
                        key={option}
                        label={option}
                        tone="tertiary"
                        active={form.infectionSigns.includes(option)}
                        onClick={() => toggleArrayValue("infectionSigns", option)}
                      />
                    ))}
                  </div>
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                <ToggleCard
                  label="Cultura da ferida realizada?"
                  description="Ative para registrar o resultado da cultura."
                  active={form.culturePerformed}
                  onClick={() => toggleBooleanField("culturePerformed")}
                />

                {form.culturePerformed ? (
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-on-surface-variant">
                      Resultado da cultura
                    </label>
                    <Input
                      value={form.cultureResult}
                      onChange={(event) =>
                        updateFormField("cultureResult", event.target.value)
                      }
                      placeholder="Informe o resultado da cultura"
                    />
                  </div>
                ) : (
                  <div className="rounded-2xl border border-outline-variant/8 bg-surface-container p-4 text-sm text-on-surface-variant">
                    Preencha o resultado apenas quando houver cultura realizada.
                  </div>
                )}
              </div>
            </div>
          </AccordionSection>

          <AccordionSection
            id="moisture"
            title="M - Umidade"
            subtitle="Quantidade, tipo e consistencia do exsudato"
            icon="water_drop"
            isOpen={expandedSection === "moisture"}
            onToggle={handleSectionToggle}
            complete={moistureSectionReady}
          >
            <div className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <SelectField
                  label="Quantidade"
                  value={form.exudateAmount}
                  options={EXUDATE_AMOUNT_OPTIONS}
                  onChange={(value) => updateFormField("exudateAmount", value)}
                />
                <SelectField
                  label="Tipo"
                  value={form.exudateType}
                  options={EXUDATE_TYPE_OPTIONS}
                  onChange={(value) => updateFormField("exudateType", value)}
                />
                <SelectField
                  label="Consistencia"
                  value={form.exudateConsistency}
                  options={EXUDATE_CONSISTENCY_OPTIONS}
                  onChange={(value) =>
                    updateFormField("exudateConsistency", value)
                  }
                />
              </div>

              <div className="rounded-3xl border border-outline-variant/8 bg-surface-container p-5">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-on-surface-variant">
                  Resumo do exsudato
                </p>
                <p className="mt-3 text-sm text-on-surface">
                  {[form.exudateAmount, form.exudateType, form.exudateConsistency]
                    .filter(Boolean)
                    .join(" • ") || "Selecione quantidade, tipo e consistencia."}
                </p>
              </div>
            </div>
          </AccordionSection>

          <AccordionSection
            id="edge"
            title="E - Bordas"
            subtitle="Bordas, tunel/cavidade e pele perilesional"
            icon="scan"
            isOpen={expandedSection === "edge"}
            onToggle={handleSectionToggle}
            complete={edgeSectionReady}
          >
            <div className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <SelectField
                  label="Caracteristicas das bordas"
                  value={form.edgeCharacteristics}
                  options={EDGE_CHARACTERISTICS_OPTIONS}
                  onChange={(value) =>
                    updateFormField("edgeCharacteristics", value)
                  }
                />
                <SelectField
                  label="Fixacao das bordas"
                  value={form.edgeAttachment}
                  options={EDGE_ATTACHMENT_OPTIONS}
                  onChange={(value) => updateFormField("edgeAttachment", value)}
                />
                <SelectField
                  label="Velocidade de cicatrizacao"
                  value={form.healingSpeed}
                  options={HEALING_SPEED_OPTIONS}
                  onChange={(value) => updateFormField("healingSpeed", value)}
                />
              </div>

              <div className="grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                <div className="space-y-4">
                  <ToggleCard
                    label="Presenca de tunel ou cavidade?"
                    description="Ative para registrar localizacao do tunel/cavidade."
                    active={form.tunnelCavity}
                    onClick={() => toggleBooleanField("tunnelCavity")}
                  />

                  {form.tunnelCavity && (
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-on-surface-variant">
                        Localizacao do tunel/cavidade
                      </label>
                      <Input
                        value={form.tunnelLocation}
                        onChange={(event) =>
                          updateFormField("tunnelLocation", event.target.value)
                        }
                        placeholder="Descreva a localizacao"
                      />
                    </div>
                  )}

                  <SelectField
                    label="Umidade da pele perilesional"
                    value={form.periwoundMoisture}
                    options={PERIWOUND_MOISTURE_OPTIONS}
                    onChange={(value) =>
                      updateFormField("periwoundMoisture", value)
                    }
                  />

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-on-surface-variant">
                      Extensao da alteracao
                    </label>
                    <Input
                      value={form.periwoundExtension}
                      onChange={(event) =>
                        updateFormField("periwoundExtension", event.target.value)
                      }
                      placeholder="Ex.: 2 cm ao redor da lesao"
                    />
                  </div>
                </div>

                <div className="rounded-3xl border border-outline-variant/8 bg-surface-container p-5">
                  <p className="text-sm font-semibold text-on-surface">
                    Condicao da pele perilesional
                  </p>
                  <p className="mt-1 text-sm text-on-surface-variant">
                    Selecione os aspectos observados, seguindo os mesmos campos do
                    mobile.
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {PERIWOUND_SKIN_OPTIONS.map((option) => (
                      <ChipToggle
                        key={option}
                        label={option}
                        tone="secondary"
                        active={form.periwoundSkin.includes(option)}
                        onClick={() => toggleArrayValue("periwoundSkin", option)}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </AccordionSection>

          <AccordionSection
            id="repair"
            title="R - Registro e retorno"
            subtitle="Registro clinico, profissional responsavel e retorno"
            icon="edit_note"
            isOpen={expandedSection === "repair"}
            onToggle={handleSectionToggle}
            complete={repairSectionReady}
          >
            <div className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Data da consulta
                  </label>
                  <Input
                    value={evaluationDate}
                    readOnly
                    className="bg-surface-container-high/70"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Hora da consulta
                  </label>
                  <Input
                    type="time"
                    value={form.consultationTime}
                    onChange={(event) =>
                      updateFormField("consultationTime", event.target.value)
                    }
                  />
                </div>
                <div className="space-y-2 xl:col-span-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Profissional responsavel
                  </label>
                  <Input
                    value={form.professionalName}
                    onChange={(event) =>
                      updateFormField("professionalName", event.target.value)
                    }
                    placeholder="Nome do profissional"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    COREN/CRM
                  </label>
                  <Input
                    value={form.professionalRegistry}
                    onChange={(event) =>
                      updateFormField("professionalRegistry", event.target.value)
                    }
                    placeholder="Registro profissional"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Data de retorno
                  </label>
                  <Input
                    type="date"
                    value={form.followUpDate}
                    onChange={(event) =>
                      updateFormField("followUpDate", event.target.value)
                    }
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-on-surface-variant">
                  Observacoes clinicas
                </label>
                <Textarea
                  rows={4}
                  value={form.notes}
                  onChange={(event) => updateFormField("notes", event.target.value)}
                  placeholder="Condutas, observacoes e orientacoes"
                />
              </div>
            </div>
          </AccordionSection>

          <AccordionSection
            id="social"
            title="S - Fatores sociais"
            subtitle="Atividade, adesao, suporte social e contexto nutricional"
            icon="diversity_3"
            isOpen={expandedSection === "social"}
            onToggle={handleSectionToggle}
            complete={socialSectionReady}
          >
            <div className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2">
                <SelectField
                  label="Nivel de atividade"
                  value={form.activityLevel}
                  options={ACTIVITY_LEVEL_OPTIONS}
                  onChange={(value) => updateFormField("activityLevel", value)}
                />
                <SelectField
                  label="Compreensao e adesao"
                  value={form.adherenceUnderstanding}
                  options={ADHERENCE_OPTIONS}
                  onChange={(value) =>
                    updateFormField("adherenceUnderstanding", value)
                  }
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-on-surface-variant">
                  Suporte social e cuidadores
                </label>
                <Textarea
                  rows={3}
                  value={form.socialSupport}
                  onChange={(event) =>
                    updateFormField("socialSupport", event.target.value)
                  }
                  placeholder="Descreva rede de apoio e cuidadores"
                />
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <ToggleCard
                  label="Pratica atividade fisica?"
                  active={form.physicalActivity}
                  onClick={() => toggleBooleanField("physicalActivity")}
                />
                {form.physicalActivity && (
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-on-surface-variant">
                        Qual atividade?
                      </label>
                      <Input
                        value={form.physicalActivityDescription}
                        onChange={(event) =>
                          updateFormField(
                            "physicalActivityDescription",
                            event.target.value,
                          )
                        }
                        placeholder="Ex.: caminhada"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-on-surface-variant">
                        Frequencia
                      </label>
                      <Input
                        value={form.physicalActivityFrequency}
                        onChange={(event) =>
                          updateFormField(
                            "physicalActivityFrequency",
                            event.target.value,
                          )
                        }
                        placeholder="Ex.: 3x por semana"
                      />
                    </div>
                  </div>
                )}

                <ToggleCard
                  label="Ingere alcool?"
                  active={form.alcoholUse}
                  onClick={() => toggleBooleanField("alcoholUse")}
                />
                {form.alcoholUse && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-on-surface-variant">
                      Frequencia do uso de alcool
                    </label>
                    <Input
                      value={form.alcoholFrequency}
                      onChange={(event) =>
                        updateFormField("alcoholFrequency", event.target.value)
                      }
                      placeholder="Ex.: social aos fins de semana"
                    />
                  </div>
                )}

                <ToggleCard
                  label="Paciente e fumante?"
                  active={form.smoker}
                  onClick={() => toggleBooleanField("smoker")}
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Avaliacao nutricional
                  </label>
                  <Textarea
                    rows={3}
                    value={form.nutritionalAssessment}
                    onChange={(event) =>
                      updateFormField("nutritionalAssessment", event.target.value)
                    }
                    placeholder="Peso, alimentacao, suplementacao etc."
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Ingestao de agua por dia
                  </label>
                  <Input
                    value={form.waterIntake}
                    onChange={(event) =>
                      updateFormField("waterIntake", event.target.value)
                    }
                    placeholder="Ex.: 2 litros"
                  />
                </div>
              </div>
            </div>
          </AccordionSection>

          <div className="rounded-3xl border border-outline-variant/8 bg-surface-container-low p-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-base font-bold text-on-surface">
                  Pronto para finalizar?
                </p>
                <p className="mt-1 text-sm text-on-surface-variant">
                  O envio preserva upload de fotos, rascunho e sincronizacao com a
                  API clinica/Firebase.
                </p>
              </div>

              <div className="flex flex-wrap gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void saveDraft()}
                  disabled={savingDraft}
                >
                  {savingDraft ? "Salvando..." : "Salvar rascunho"}
                </Button>
                <Button
                  type="button"
                  onClick={() => void finalizeEvaluation()}
                  disabled={!finalChecklistReady || savingEvaluation}
                >
                  {savingEvaluation ? "Finalizando..." : "Finalizar avaliacao"}
                </Button>
              </div>
            </div>

            {statusMessage && (
              <div className="mt-4 rounded-2xl bg-primary/10 px-4 py-3 text-sm font-medium text-primary">
                {statusMessage}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
