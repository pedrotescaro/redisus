"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { listPatients } from "@/services/firebase/patient-service";
import { analyzeWoundImage, type NeuralAnalysisResult } from "@/services/ai/heal-ai-service";
import type { Patient } from "@/types/patient";

type Step = {
  id: number;
  title: string;
  status: "completed" | "in_progress" | "pending";
};

type PhotoSlot = {
  id: string;
  label: string;
  file: File | null;
  preview: string | null;
};

type PushForm = {
  area: number;
  exudate: number;
  tissue: number;
};

type BradenForm = {
  sensoryPerception: number;
  moisture: number;
  activity: number;
  mobility: number;
  nutrition: number;
  frictionShear: number;
};

type BwatItem = {
  key: string;
  label: string;
  min: number;
  max: number;
};

type BwatForm = Record<string, number>;

type TimersForm = {
  tTissueBed: string;
  tDebridement: string;
  tGranulationPct: number;
  tSloughPct: number;
  tNecrosisPct: number;
  tEpithelializationPct: number;
  iInfectionLevel: string;
  iInflammationSigns: string[];
  mExudateLevel: string;
  mPerilesionalCare: string;
  eEdgeCondition: string;
  eAdvancement: string;
  rGoal: string;
  rCoverType: string;
  sAdherenceRisk: string;
  sBarriers: string[];
};

const DRAFT_KEY = "healplus-evaluation-draft-v1";
const HISTORY_KEY = "healplus-evaluation-history-v1";

const BWAT_ITEMS: BwatItem[] = [
  { key: "size", label: "Tamanho", min: 1, max: 5 },
  { key: "depth", label: "Profundidade", min: 1, max: 5 },
  { key: "edges", label: "Bordas", min: 1, max: 5 },
  { key: "undermining", label: "Descolamento", min: 1, max: 5 },
  { key: "necroticType", label: "Tipo de tecido necrótico", min: 1, max: 5 },
  { key: "necroticAmount", label: "Quantidade de necrose", min: 1, max: 5 },
  { key: "exudateType", label: "Tipo de exsudato", min: 1, max: 5 },
  { key: "exudateAmount", label: "Quantidade de exsudato", min: 1, max: 5 },
  { key: "skinColor", label: "Cor da pele ao redor", min: 1, max: 5 },
  { key: "peripheralEdema", label: "Edema periférico", min: 1, max: 5 },
  { key: "peripheralInduration", label: "Endurecimento periférico", min: 1, max: 5 },
  { key: "granulation", label: "Tecido de granulação", min: 1, max: 5 },
  { key: "epithelialization", label: "Epitelização", min: 1, max: 5 },
];

const makeDefaultBwat = (): BwatForm =>
  BWAT_ITEMS.reduce<BwatForm>((acc, item) => {
    acc[item.key] = 1;
    return acc;
  }, {});

const getBradenRisk = (score: number) => {
  if (score <= 9) return "Muito alto";
  if (score <= 12) return "Alto";
  if (score <= 14) return "Moderado";
  if (score <= 18) return "Baixo";
  return "Sem risco";
};

const getPushInterpretation = (score: number) => {
  if (score <= 4) return "Evolução favorável";
  if (score <= 10) return "Requer monitoramento";
  return "Atenção clínica intensiva";
};

const getBwatInterpretation = (score: number) => {
  if (score <= 20) return "Baixa gravidade";
  if (score <= 35) return "Gravidade moderada";
  if (score <= 50) return "Gravidade alta";
  return "Gravidade muito alta";
};

export default function NewEvaluationPage() {
  const [currentStep, setCurrentStep] = useState(1);
  const [patientSearch, setPatientSearch] = useState("");
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loadingPatients, setLoadingPatients] = useState(true);
  const [evaluationDate, setEvaluationDate] = useState(
    new Date().toISOString().split("T")[0]
  );
  const [woundType, setWoundType] = useState("");
  const [woundLocation, setWoundLocation] = useState("");
  const [clinicalDescription, setClinicalDescription] = useState("");
  const [pushForm, setPushForm] = useState<PushForm>({
    area: 0,
    exudate: 0,
    tissue: 0,
  });
  const [bradenForm, setBradenForm] = useState<BradenForm>({
    sensoryPerception: 1,
    moisture: 1,
    activity: 1,
    mobility: 1,
    nutrition: 1,
    frictionShear: 1,
  });
  const [bwatForm, setBwatForm] = useState<BwatForm>(makeDefaultBwat());
  const [timersForm, setTimersForm] = useState<TimersForm>({
    tTissueBed: "",
    tDebridement: "",
    tGranulationPct: 0,
    tSloughPct: 0,
    tNecrosisPct: 0,
    tEpithelializationPct: 0,
    iInfectionLevel: "",
    iInflammationSigns: [],
    mExudateLevel: "",
    mPerilesionalCare: "",
    eEdgeCondition: "",
    eAdvancement: "",
    rGoal: "",
    rCoverType: "",
    sAdherenceRisk: "",
    sBarriers: [],
  });
  const [savingDraft, setSavingDraft] = useState(false);
  const [savingEvaluation, setSavingEvaluation] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [aiAnalysis, setAiAnalysis] = useState<NeuralAnalysisResult | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [photoSlots, setPhotoSlots] = useState<PhotoSlot[]>([
    { id: "frontal", label: "Foto Frontal", file: null, preview: null },
    { id: "lateral", label: "Foto Lateral", file: null, preview: null },
    { id: "detail", label: "Foto Detalhe", file: null, preview: null },
  ]);

  const fileInputRefs = useRef<{ [key: string]: HTMLInputElement | null }>({});

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
    if (typeof window === "undefined") return;
    const draftRaw = localStorage.getItem(DRAFT_KEY);
    if (!draftRaw) return;
    try {
      const draft = JSON.parse(draftRaw) as {
        patientSearch: string;
        selectedPatientId: string;
        evaluationDate: string;
        woundType: string;
        woundLocation: string;
        clinicalDescription: string;
        pushForm: PushForm;
        bradenForm: BradenForm;
        bwatForm: BwatForm;
        timersForm: TimersForm;
      };
      setPatientSearch(draft.patientSearch ?? "");
      setSelectedPatientId(draft.selectedPatientId ?? "");
      setEvaluationDate(draft.evaluationDate ?? evaluationDate);
      setWoundType(draft.woundType ?? "");
      setWoundLocation(draft.woundLocation ?? "");
      setClinicalDescription(draft.clinicalDescription ?? "");
      setPushForm(draft.pushForm ?? { area: 0, exudate: 0, tissue: 0 });
      setBradenForm(
        draft.bradenForm ?? {
          sensoryPerception: 1,
          moisture: 1,
          activity: 1,
          mobility: 1,
          nutrition: 1,
          frictionShear: 1,
        }
      );
      setBwatForm(draft.bwatForm ?? makeDefaultBwat());
      setTimersForm(
        draft.timersForm ?? {
          tTissueBed: "",
          tDebridement: "",
          tGranulationPct: 0,
          tSloughPct: 0,
          tNecrosisPct: 0,
          tEpithelializationPct: 0,
          iInfectionLevel: "",
          iInflammationSigns: [],
          mExudateLevel: "",
          mPerilesionalCare: "",
          eEdgeCondition: "",
          eAdvancement: "",
          rGoal: "",
          rCoverType: "",
          sAdherenceRisk: "",
          sBarriers: [],
        }
      );
      setStatusMessage("Rascunho restaurado automaticamente.");
    } catch {
      localStorage.removeItem(DRAFT_KEY);
    }
  }, [evaluationDate]);

  const selectedPatient = useMemo(
    () => patients.find((item) => item.id === selectedPatientId) ?? null,
    [patients, selectedPatientId]
  );

  const filteredPatients = useMemo(() => {
    const normalized = patientSearch.trim().toLowerCase();
    if (!normalized) return patients;
    return patients.filter((item) =>
      item.name.toLowerCase().includes(normalized)
    );
  }, [patients, patientSearch]);

  const pushScore = pushForm.area + pushForm.exudate + pushForm.tissue;
  const bradenScore = Object.values(bradenForm).reduce((acc, curr) => acc + curr, 0);
  const bwatScore = Object.values(bwatForm).reduce((acc, curr) => acc + curr, 0);
  const uploadedPhotos = photoSlots.filter((item) => item.file).length;
  const tissueTotalPct =
    timersForm.tGranulationPct +
    timersForm.tSloughPct +
    timersForm.tNecrosisPct +
    timersForm.tEpithelializationPct;

  const isStep1Valid = Boolean(selectedPatientId && evaluationDate);
  const isStep2Valid = Boolean(woundType && woundLocation.trim() && clinicalDescription.trim());
  const isStep3Valid = uploadedPhotos > 0;
  const isStep4Valid = Boolean(
    timersForm.tTissueBed &&
      timersForm.tDebridement &&
      tissueTotalPct === 100 &&
      timersForm.iInfectionLevel &&
      timersForm.mExudateLevel &&
      timersForm.mPerilesionalCare &&
      timersForm.eEdgeCondition &&
      timersForm.eAdvancement &&
      timersForm.rGoal &&
      timersForm.rCoverType &&
      timersForm.sAdherenceRisk
  );

  const canAdvance =
    (currentStep === 1 && isStep1Valid) ||
    (currentStep === 2 && isStep2Valid) ||
    (currentStep === 3 && isStep3Valid) ||
    (currentStep === 4 && isStep4Valid);

  const finalChecklistReady = isStep1Valid && isStep2Valid && isStep3Valid && isStep4Valid;

  const steps: Step[] = [
    {
      id: 1,
      title: "Paciente e Dados",
      status:
        currentStep === 1
          ? "in_progress"
          : currentStep > 1
            ? "completed"
            : "pending",
    },
    {
      id: 2,
      title: "Avaliação Clínica",
      status:
        currentStep === 2
          ? "in_progress"
          : currentStep > 2
            ? "completed"
            : "pending",
    },
    {
      id: 3,
      title: "Evidência e IA",
      status:
        currentStep === 3
          ? "in_progress"
          : currentStep > 3
            ? "completed"
            : "pending",
    },
    {
      id: 4,
      title: "TIMERS e Fechamento",
      status:
        currentStep === 4
          ? "in_progress"
          : currentStep > 4
            ? "completed"
            : "pending",
    },
  ];

  const getStepStatusLabel = (status: Step["status"]) => {
    switch (status) {
      case "completed":
        return "CONCLUÍDO";
      case "in_progress":
        return "EM PROGRESSO";
      default:
        return "AGUARDANDO";
    }
  };

  const getStepStatusColor = (status: Step["status"]) => {
    switch (status) {
      case "completed":
        return "text-green-400";
      case "in_progress":
        return "text-primary";
      default:
        return "text-gray-500";
    }
  };

  const handlePhotoUpload = (slotId: string, file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      setPhotoSlots((prev) =>
        prev.map((slot) =>
          slot.id === slotId
            ? { ...slot, file, preview: e.target?.result as string }
            : slot
        )
      );
    };
    reader.readAsDataURL(file);
  };

  const handleFileInputChange = (
    slotId: string,
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    if (file) {
      handlePhotoUpload(slotId, file);
    }
  };

  const removePhoto = (slotId: string) => {
    setPhotoSlots((prev) =>
      prev.map((slot) =>
        slot.id === slotId ? { ...slot, file: null, preview: null } : slot
      )
    );
  };

  const saveDraft = () => {
    if (typeof window === "undefined") return;
    setSavingDraft(true);
    setStatusMessage(null);
    try {
      localStorage.setItem(
        DRAFT_KEY,
        JSON.stringify({
          patientSearch,
          selectedPatientId,
          evaluationDate,
          woundType,
          woundLocation,
          clinicalDescription,
          pushForm,
          bradenForm,
          bwatForm,
          timersForm,
        })
      );
      setStatusMessage("Rascunho salvo com sucesso.");
    } finally {
      setSavingDraft(false);
    }
  };

  const finalizeEvaluation = () => {
    if (!finalChecklistReady || typeof window === "undefined") {
      setStatusMessage("Finalize todas as etapas e preencha o protocolo TIMERS.");
      return;
    }
    setSavingEvaluation(true);
    setStatusMessage(null);
    try {
      const existing = localStorage.getItem(HISTORY_KEY);
      const history = existing ? (JSON.parse(existing) as unknown[]) : [];
      const entry = {
        id: `eval-${Date.now()}`,
        createdAt: new Date().toISOString(),
        patientId: selectedPatientId,
        patientName: selectedPatient?.name ?? "Paciente",
        evaluationDate,
        woundType,
        woundLocation,
        clinicalDescription,
        pushScore,
        bwatScore,
        bradenScore,
        bradenRisk: getBradenRisk(bradenScore),
        timersForm,
      };
      localStorage.setItem(HISTORY_KEY, JSON.stringify([entry, ...history]));
      localStorage.removeItem(DRAFT_KEY);
      setStatusMessage("Avaliação finalizada e registrada localmente.");
    } finally {
      setSavingEvaluation(false);
    }
  };

  const runAiAnalysis = async () => {
    const firstPhoto = photoSlots.find((slot) => slot.file)?.file;
    if (!firstPhoto) {
      setAiError("Envie ao menos uma foto para análise por IA.");
      return;
    }
    setAiLoading(true);
    setAiError(null);
    setAiAnalysis(null);
    try {
      const result = await analyzeWoundImage(firstPhoto);
      setAiAnalysis(result);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Falha ao executar análise de IA.";
      setAiError(message);
    } finally {
      setAiLoading(false);
    }
  };

  const handleContinue = () => {
    if (!canAdvance) {
      setStatusMessage("Preencha os campos obrigatórios da etapa atual.");
      return;
    }
    if (currentStep < 4) {
      setCurrentStep((prev) => prev + 1);
      setStatusMessage(null);
      return;
    }
    finalizeEvaluation();
  };

  const handleBack = () => {
    setCurrentStep((prev) => Math.max(1, prev - 1));
  };

  const setTissuePct = (
    key:
      | "tGranulationPct"
      | "tSloughPct"
      | "tNecrosisPct"
      | "tEpithelializationPct",
    rawValue: string
  ) => {
    const parsed = Number(rawValue);
    const safe = Number.isNaN(parsed) ? 0 : Math.max(0, Math.min(100, parsed));
    setTimersForm((current) => ({
      ...current,
      [key]: safe,
    }));
  };

  const toggleArrayOption = (
    field: "iInflammationSigns" | "sBarriers",
    option: string
  ) => {
    setTimersForm((current) => {
      const list = current[field];
      const exists = list.includes(option);
      return {
        ...current,
        [field]: exists ? list.filter((item) => item !== option) : [...list, option],
      };
    });
  };

  const woundTypes = [
    { value: "", label: "Selecione o tipo de ferida" },
    { value: "pressure_ulcer", label: "Úlcera por Pressão" },
    { value: "diabetic_ulcer", label: "Úlcera Diabética" },
    { value: "venous_ulcer", label: "Úlcera Venosa" },
    { value: "arterial_ulcer", label: "Úlcera Arterial" },
    { value: "surgical_wound", label: "Ferida Cirúrgica" },
    { value: "traumatic_wound", label: "Ferida Traumática" },
    { value: "burn", label: "Queimadura" },
    { value: "other", label: "Outro" },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold font-headline text-on-surface">
            Nova Avaliação
          </h1>
          <p className="text-on-surface-variant mt-1">
            Registre uma avaliação clínica detalhada com análise por IA
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs font-bold text-primary bg-primary/10 px-4 py-2 rounded-full">
          <span className="material-symbols-outlined text-sm">verified</span>
          Protocolo clínico com TIMERS ativo
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-8">
        {/* Progress Sidebar */}
        <div className="bg-surface-container-low rounded-xl p-6 h-fit border border-outline-variant/5">
          <h3 className="text-sm font-bold uppercase tracking-wider text-gray-500 mb-6">
            Progresso
          </h3>
          <div className="space-y-4">
            {steps.map((step, index) => (
              <div
                key={step.id}
                className={`flex items-start gap-4 p-3 rounded-lg transition-all cursor-pointer ${
                  step.status === "in_progress"
                    ? "bg-primary/10 border border-primary/20"
                    : step.status === "completed"
                      ? "bg-green-500/5"
                      : "hover:bg-surface-container"
                }`}
                onClick={() => setCurrentStep(step.id)}
              >
                {/* Step Number/Icon */}
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                    step.status === "completed"
                      ? "bg-green-500 text-white"
                      : step.status === "in_progress"
                        ? "bg-primary text-on-primary"
                        : "bg-surface-container-high text-gray-500"
                  }`}
                >
                  {step.status === "completed" ? (
                    <span className="material-symbols-outlined text-sm">
                      check
                    </span>
                  ) : (
                    <span className="text-sm font-bold">{step.id}</span>
                  )}
                </div>

                {/* Step Info */}
                <div className="flex-grow min-w-0">
                  <p
                    className={`font-semibold text-sm ${
                      step.status === "in_progress"
                        ? "text-primary"
                        : step.status === "completed"
                          ? "text-green-400"
                          : "text-gray-400"
                    }`}
                  >
                    {step.title}
                  </p>
                  <p
                    className={`text-[10px] font-bold uppercase tracking-wider mt-0.5 ${getStepStatusColor(step.status)}`}
                  >
                    {getStepStatusLabel(step.status)}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Vertical Line Connector */}
          <div className="mt-6 pt-6 border-t border-outline-variant/10">
            <p className="text-xs text-gray-500 text-center">
              Passo {currentStep} de {steps.length}
            </p>
          </div>
        </div>

        {/* Form Content */}
        <div className="space-y-8">
          {/* Step 1 */}
          {currentStep === 1 && (
          <section className="bg-surface-container-low rounded-xl p-8 border border-outline-variant/5">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
                <span className="material-symbols-outlined">
                  person_search
                </span>
              </div>
              <div>
                <h2 className="text-lg font-bold font-headline text-on-surface">
                  Identificação e Contexto
                </h2>
                <p className="text-sm text-on-surface-variant">
                  Dados do paciente e informações básicas da avaliação
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Patient Search */}
              <div className="space-y-2 md:col-span-2">
                <label className="text-sm font-medium text-on-surface-variant">
                  Paciente
                </label>
                <div className="relative">
                  <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                    search
                  </span>
                  <Input
                    placeholder="Buscar paciente por nome..."
                    value={patientSearch}
                    onChange={(e) => setPatientSearch(e.target.value)}
                    className="pl-10"
                  />
                </div>
                <div className="bg-surface-container rounded-xl p-3 max-h-52 overflow-auto">
                  {loadingPatients ? (
                    <p className="text-sm text-on-surface-variant">Carregando pacientes...</p>
                  ) : filteredPatients.length === 0 ? (
                    <p className="text-sm text-on-surface-variant">Nenhum paciente encontrado.</p>
                  ) : (
                    <div className="space-y-2">
                      {filteredPatients.slice(0, 8).map((patient) => (
                        <button
                          type="button"
                          key={patient.id}
                          onClick={() => setSelectedPatientId(patient.id)}
                          className={`w-full text-left rounded-lg px-3 py-2 transition-all ${
                            selectedPatientId === patient.id
                              ? "bg-primary/15 text-primary"
                              : "hover:bg-surface-container-high text-on-surface"
                          }`}
                        >
                          <p className="text-sm font-semibold">{patient.name}</p>
                          <p className="text-xs text-on-surface-variant">{patient.phone || "Sem telefone"} • {patient.email || "Sem e-mail"}</p>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Evaluation Date */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-on-surface-variant">
                  Data da Avaliação
                </label>
                <Input
                  type="date"
                  value={evaluationDate}
                  onChange={(e) => setEvaluationDate(e.target.value)}
                />
              </div>

              {/* Wound Type */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-on-surface-variant">
                  Tipo de Ferida
                </label>
                <div className="relative">
                  <select
                    value={woundType}
                    onChange={(e) => setWoundType(e.target.value)}
                    className="w-full rounded-xl border border-outline-variant/15 bg-surface-container-high px-4 py-2.5 text-sm text-on-surface outline-none transition-all focus:border-primary focus:ring-2 focus:ring-primary/20 appearance-none cursor-pointer"
                  >
                    {woundTypes.map((type) => (
                      <option key={type.value} value={type.value}>
                        {type.label}
                      </option>
                    ))}
                  </select>
                  <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none">
                    expand_more
                  </span>
                </div>
              </div>

              {/* Clinical Description */}
              <div className="space-y-2 md:col-span-2">
                <label className="text-sm font-medium text-on-surface-variant">
                  Descrição Clínica
                </label>
                <Textarea
                  rows={4}
                  placeholder="Descreva as características observadas, localização anatômica, histórico e outras informações relevantes..."
                  value={clinicalDescription}
                  onChange={(e) => setClinicalDescription(e.target.value)}
                />
              </div>
            </div>
          </section>
          )}

          {/* Step 2 */}
          {currentStep === 2 && (
          <section className="bg-surface-container-low rounded-xl p-8 border border-outline-variant/5">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-secondary/20 flex items-center justify-center text-secondary">
                <span className="material-symbols-outlined">clinical_notes</span>
              </div>
              <div>
                <h2 className="text-lg font-bold font-headline text-on-surface">
                  Escalas Clínicas Validadas
                </h2>
                <p className="text-sm text-on-surface-variant">
                  PUSH Tool 3.0, BWAT e Braden com cálculo automático.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2 md:col-span-2">
                <label className="text-sm font-medium text-on-surface-variant">
                  Localização anatômica
                </label>
                <Input
                  placeholder="Ex.: calcâneo direito, região sacral..."
                  value={woundLocation}
                  onChange={(e) => setWoundLocation(e.target.value)}
                />
              </div>
              <div className="bg-surface-container rounded-xl p-4 space-y-3">
                <p className="text-sm font-bold text-on-surface">PUSH Tool 3.0 (0-17)</p>
                <label className="text-xs text-on-surface-variant">Área (0-10)</label>
                <Input type="number" min={0} max={10} value={pushForm.area} onChange={(e) => setPushForm((c) => ({ ...c, area: Number(e.target.value) || 0 }))} />
                <label className="text-xs text-on-surface-variant">Exsudato (0-3)</label>
                <Input type="number" min={0} max={3} value={pushForm.exudate} onChange={(e) => setPushForm((c) => ({ ...c, exudate: Number(e.target.value) || 0 }))} />
                <label className="text-xs text-on-surface-variant">Tecido (0-4)</label>
                <Input type="number" min={0} max={4} value={pushForm.tissue} onChange={(e) => setPushForm((c) => ({ ...c, tissue: Number(e.target.value) || 0 }))} />
                <p className="text-sm text-primary font-bold">Score PUSH: {pushScore} • {getPushInterpretation(pushScore)}</p>
              </div>

              <div className="bg-surface-container rounded-xl p-4 space-y-3">
                <p className="text-sm font-bold text-on-surface">Braden (6-23)</p>
                {[
                  ["sensoryPerception", "Percepção sensorial"],
                  ["moisture", "Umidade"],
                  ["activity", "Atividade"],
                  ["mobility", "Mobilidade"],
                  ["nutrition", "Nutrição"],
                  ["frictionShear", "Fricção/Cisalhamento"],
                ].map(([key, label]) => (
                  <div key={key}>
                    <label className="text-xs text-on-surface-variant">{label}</label>
                    <Input
                      type="number"
                      min={1}
                      max={4}
                      value={bradenForm[key as keyof BradenForm]}
                      onChange={(e) =>
                        setBradenForm((curr) => ({
                          ...curr,
                          [key]: Number(e.target.value) || 1,
                        }))
                      }
                    />
                  </div>
                ))}
                <p className="text-sm text-primary font-bold">
                  Score Braden: {bradenScore} • Risco {getBradenRisk(bradenScore)}
                </p>
              </div>
            </div>

            <div className="mt-6 bg-surface-container rounded-xl p-4">
              <p className="text-sm font-bold mb-3">BWAT (13 itens)</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {BWAT_ITEMS.map((item) => (
                  <div key={item.key} className="space-y-1">
                    <label className="text-xs text-on-surface-variant">
                      {item.label} ({item.min}-{item.max})
                    </label>
                    <Input
                      type="number"
                      min={item.min}
                      max={item.max}
                      value={bwatForm[item.key]}
                      onChange={(e) =>
                        setBwatForm((curr) => ({
                          ...curr,
                          [item.key]: Number(e.target.value) || item.min,
                        }))
                      }
                    />
                  </div>
                ))}
              </div>
              <p className="text-sm text-primary font-bold mt-4">
                Score BWAT: {bwatScore} • {getBwatInterpretation(bwatScore)}
              </p>
            </div>
          </section>
          )}

          {/* Step 3 */}
          {currentStep === 3 && (
          <section className="bg-surface-container-low rounded-xl p-8 border border-outline-variant/5">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-tertiary/10 flex items-center justify-center text-tertiary">
                  <span className="material-symbols-outlined">
                    add_a_photo
                  </span>
                </div>
                <div>
                  <h2 className="text-lg font-bold font-headline text-on-surface">
                    Evidência Fotográfica
                  </h2>
                  <p className="text-sm text-on-surface-variant">
                    Adicione fotos da ferida para análise por IA
                  </p>
                </div>
              </div>
              <span className="text-xs text-gray-500 bg-surface-container-high px-3 py-1 rounded-full">
                MÁX 10MB POR ARQUIVO
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {photoSlots.map((slot) => (
                <div key={slot.id} className="space-y-2">
                  <label className="text-sm font-medium text-on-surface-variant">
                    {slot.label}
                  </label>
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    ref={(el) => {
                      fileInputRefs.current[slot.id] = el;
                    }}
                    onChange={(e) => handleFileInputChange(slot.id, e)}
                  />
                  {slot.preview ? (
                    <div className="relative aspect-square rounded-xl overflow-hidden border border-outline-variant/10 group">
                      <img
                        src={slot.preview}
                        alt={slot.label}
                        className="w-full h-full object-cover"
                      />
                      <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                        <button
                          onClick={() =>
                            fileInputRefs.current[slot.id]?.click()
                          }
                          className="p-2 bg-surface-container rounded-full hover:bg-surface-container-high transition-colors"
                        >
                          <span className="material-symbols-outlined text-on-surface">
                            edit
                          </span>
                        </button>
                        <button
                          onClick={() => removePhoto(slot.id)}
                          className="p-2 bg-error/20 rounded-full hover:bg-error/30 transition-colors"
                        >
                          <span className="material-symbols-outlined text-error">
                            delete
                          </span>
                        </button>
                      </div>
                      <div className="absolute bottom-2 left-2 right-2">
                        <div className="bg-green-500/90 text-white text-xs font-bold px-2 py-1 rounded-full flex items-center gap-1 w-fit">
                          <span className="material-symbols-outlined text-xs">
                            check_circle
                          </span>
                          Enviado
                        </div>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={() => fileInputRefs.current[slot.id]?.click()}
                      className="w-full aspect-square rounded-xl border-2 border-dashed border-outline-variant/20 bg-surface-container hover:bg-surface-container-high hover:border-primary/30 transition-all flex flex-col items-center justify-center gap-3 group"
                    >
                      <div className="w-12 h-12 rounded-full bg-surface-container-high group-hover:bg-primary/10 flex items-center justify-center transition-colors">
                        <span className="material-symbols-outlined text-2xl text-gray-500 group-hover:text-primary transition-colors">
                          add_photo_alternate
                        </span>
                      </div>
                      <span className="text-sm text-gray-500 group-hover:text-on-surface transition-colors">
                        Clique para enviar
                      </span>
                    </button>
                  )}
                </div>
              ))}
            </div>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <Button type="button" variant="outline" onClick={() => void runAiAnalysis()} disabled={aiLoading}>
                <span className="material-symbols-outlined text-sm">biotech</span>
                {aiLoading ? "Analisando..." : "Executar análise de IA"}
              </Button>
              {aiError && <p className="text-sm text-error">{aiError}</p>}
            </div>
            {aiAnalysis && (
              <div className="mt-4 rounded-xl bg-surface-container p-4">
                <p className="text-sm font-bold text-on-surface">Resultado IA (preliminar)</p>
                <p className="text-sm text-on-surface-variant mt-1">
                  Tipo: {aiAnalysis.woundType} • Confiança: {(aiAnalysis.confidence * 100).toFixed(1)}% • Risco: {aiAnalysis.riskLevel}
                </p>
                <p className="text-xs text-on-surface-variant mt-2">
                  Granulação {aiAnalysis.tissueComposition.granulation}% • Esfacelo {aiAnalysis.tissueComposition.slough}% • Necrose {aiAnalysis.tissueComposition.necrosis}%
                </p>
              </div>
            )}
          </section>
          )}

          {/* Step 4 */}
          {currentStep === 4 && (
          <section className="bg-surface-container-low rounded-xl p-8 border border-outline-variant/5 space-y-5">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
                <span className="material-symbols-outlined">task_alt</span>
              </div>
              <div>
                <h2 className="text-lg font-bold font-headline text-on-surface">
                  Protocolo TIMERS
                </h2>
                <p className="text-sm text-on-surface-variant">
                  Preenchimento estruturado da ferida para decisão clínica.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-xl bg-surface-container p-4 space-y-2">
                <p className="text-xs uppercase tracking-widest text-on-surface-variant">T - Tissue</p>
                <label className="text-xs text-on-surface-variant">Leito predominante</label>
                <select
                  value={timersForm.tTissueBed}
                  onChange={(e) => setTimersForm((c) => ({ ...c, tTissueBed: e.target.value }))}
                  className="w-full rounded-xl border border-outline-variant/15 bg-surface-container-high px-3 py-2 text-sm text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                >
                  <option value="">Selecione</option>
                  <option value="granulacao">Granulação predominante</option>
                  <option value="esfacelo">Esfacelo predominante</option>
                  <option value="necrose">Necrose predominante</option>
                  <option value="misto">Leito misto</option>
                </select>
                <div className="pt-2 space-y-2">
                  <p className="text-xs text-on-surface-variant">
                    Distribuição tecidual (%) - total deve ser 100%
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <label className="text-[11px] text-on-surface-variant">Granulação</label>
                      <Input
                        type="number"
                        min={0}
                        max={100}
                        value={timersForm.tGranulationPct}
                        onChange={(e) => setTissuePct("tGranulationPct", e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[11px] text-on-surface-variant">Esfacelo</label>
                      <Input
                        type="number"
                        min={0}
                        max={100}
                        value={timersForm.tSloughPct}
                        onChange={(e) => setTissuePct("tSloughPct", e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[11px] text-on-surface-variant">Necrose</label>
                      <Input
                        type="number"
                        min={0}
                        max={100}
                        value={timersForm.tNecrosisPct}
                        onChange={(e) => setTissuePct("tNecrosisPct", e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-[11px] text-on-surface-variant">Epitelização</label>
                      <Input
                        type="number"
                        min={0}
                        max={100}
                        value={timersForm.tEpithelializationPct}
                        onChange={(e) =>
                          setTissuePct("tEpithelializationPct", e.target.value)
                        }
                      />
                    </div>
                  </div>
                  <div className="mt-2 h-3 w-full rounded-full overflow-hidden bg-surface-container-high flex">
                    <div
                      className="h-full bg-red-500/90 transition-all"
                      style={{ width: `${timersForm.tGranulationPct}%` }}
                      title={`Granulação ${timersForm.tGranulationPct}%`}
                    />
                    <div
                      className="h-full bg-yellow-400/90 transition-all"
                      style={{ width: `${timersForm.tSloughPct}%` }}
                      title={`Esfacelo ${timersForm.tSloughPct}%`}
                    />
                    <div
                      className="h-full bg-neutral-700 transition-all"
                      style={{ width: `${timersForm.tNecrosisPct}%` }}
                      title={`Necrose ${timersForm.tNecrosisPct}%`}
                    />
                    <div
                      className="h-full bg-pink-300 transition-all"
                      style={{ width: `${timersForm.tEpithelializationPct}%` }}
                      title={`Epitelização ${timersForm.tEpithelializationPct}%`}
                    />
                  </div>
                  <p
                    className={`text-xs font-semibold ${
                      tissueTotalPct === 100 ? "text-green-400" : "text-tertiary"
                    }`}
                  >
                    Total atual: {tissueTotalPct}% {tissueTotalPct === 100 ? "✓" : "(ajuste para 100%)"}
                  </p>
                </div>
                <label className="text-xs text-on-surface-variant">Necessidade de desbridamento</label>
                <select
                  value={timersForm.tDebridement}
                  onChange={(e) => setTimersForm((c) => ({ ...c, tDebridement: e.target.value }))}
                  className="w-full rounded-xl border border-outline-variant/15 bg-surface-container-high px-3 py-2 text-sm text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                >
                  <option value="">Selecione</option>
                  <option value="nao">Não necessário</option>
                  <option value="autolitico">Autolítico</option>
                  <option value="enzimatico">Enzimático</option>
                  <option value="instrumental">Instrumental/cirúrgico</option>
                </select>
              </div>
              <div className="rounded-xl bg-surface-container p-4 space-y-2">
                <p className="text-xs uppercase tracking-widest text-on-surface-variant">I - Infection/Inflammation</p>
                <label className="text-xs text-on-surface-variant">Nível de infecção</label>
                <select
                  value={timersForm.iInfectionLevel}
                  onChange={(e) => setTimersForm((c) => ({ ...c, iInfectionLevel: e.target.value }))}
                  className="w-full rounded-xl border border-outline-variant/15 bg-surface-container-high px-3 py-2 text-sm text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                >
                  <option value="">Selecione</option>
                  <option value="sem_sinais">Sem sinais clínicos</option>
                  <option value="suspeita_local">Suspeita local</option>
                  <option value="infeccao_confirmada">Infecção confirmada</option>
                </select>
                <p className="text-xs text-on-surface-variant pt-1">Sinais inflamatórios presentes</p>
                <div className="flex flex-wrap gap-2">
                  {["Dor", "Odor", "Calor", "Eritema", "Exsudato purulento", "Biofilme"].map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() => toggleArrayOption("iInflammationSigns", option)}
                      className={`px-2.5 py-1.5 rounded-full text-xs font-semibold transition-colors ${
                        timersForm.iInflammationSigns.includes(option)
                          ? "bg-primary/20 text-primary"
                          : "bg-surface-container-high text-on-surface-variant hover:text-on-surface"
                      }`}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              </div>
              <div className="rounded-xl bg-surface-container p-4 space-y-2">
                <p className="text-xs uppercase tracking-widest text-on-surface-variant">M - Moisture</p>
                <label className="text-xs text-on-surface-variant">Volume de exsudato</label>
                <select
                  value={timersForm.mExudateLevel}
                  onChange={(e) => setTimersForm((c) => ({ ...c, mExudateLevel: e.target.value }))}
                  className="w-full rounded-xl border border-outline-variant/15 bg-surface-container-high px-3 py-2 text-sm text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                >
                  <option value="">Selecione</option>
                  <option value="seco">Seco/ausente</option>
                  <option value="baixo">Baixo</option>
                  <option value="moderado">Moderado</option>
                  <option value="alto">Alto</option>
                </select>
                <label className="text-xs text-on-surface-variant">Conduta perilesional</label>
                <select
                  value={timersForm.mPerilesionalCare}
                  onChange={(e) => setTimersForm((c) => ({ ...c, mPerilesionalCare: e.target.value }))}
                  className="w-full rounded-xl border border-outline-variant/15 bg-surface-container-high px-3 py-2 text-sm text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                >
                  <option value="">Selecione</option>
                  <option value="barreira_cutanea">Barreira cutânea</option>
                  <option value="espuma_absorvente">Espuma absorvente</option>
                  <option value="hidrofibra_alginato">Hidrofibra/Alginato</option>
                  <option value="hidrocoloide">Hidrocoloide</option>
                </select>
              </div>
              <div className="rounded-xl bg-surface-container p-4 space-y-2">
                <p className="text-xs uppercase tracking-widest text-on-surface-variant">E - Edge</p>
                <label className="text-xs text-on-surface-variant">Condição de borda</label>
                <select
                  value={timersForm.eEdgeCondition}
                  onChange={(e) => setTimersForm((c) => ({ ...c, eEdgeCondition: e.target.value }))}
                  className="w-full rounded-xl border border-outline-variant/15 bg-surface-container-high px-3 py-2 text-sm text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                >
                  <option value="">Selecione</option>
                  <option value="regular">Regular/íntegra</option>
                  <option value="macerada">Macerada</option>
                  <option value="hiperqueratose">Hiperqueratose</option>
                  <option value="epibole">Epibole</option>
                </select>
                <label className="text-xs text-on-surface-variant">Avanço de cicatrização</label>
                <select
                  value={timersForm.eAdvancement}
                  onChange={(e) => setTimersForm((c) => ({ ...c, eAdvancement: e.target.value }))}
                  className="w-full rounded-xl border border-outline-variant/15 bg-surface-container-high px-3 py-2 text-sm text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                >
                  <option value="">Selecione</option>
                  <option value="progressao">Em progressão</option>
                  <option value="estavel">Estável</option>
                  <option value="regressao">Em regressão</option>
                </select>
              </div>
              <div className="rounded-xl bg-surface-container p-4 space-y-2">
                <p className="text-xs uppercase tracking-widest text-on-surface-variant">R - Repair/Regeneration</p>
                <label className="text-xs text-on-surface-variant">Objetivo principal</label>
                <select
                  value={timersForm.rGoal}
                  onChange={(e) => setTimersForm((c) => ({ ...c, rGoal: e.target.value }))}
                  className="w-full rounded-xl border border-outline-variant/15 bg-surface-container-high px-3 py-2 text-sm text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                >
                  <option value="">Selecione</option>
                  <option value="desbridar">Desbridar tecido desvitalizado</option>
                  <option value="estimular_granulacao">Estimular granulação</option>
                  <option value="controlar_infeccao">Controlar infecção</option>
                  <option value="proteger_epitelizacao">Proteger epitelização</option>
                </select>
                <label className="text-xs text-on-surface-variant">Cobertura planejada</label>
                <select
                  value={timersForm.rCoverType}
                  onChange={(e) => setTimersForm((c) => ({ ...c, rCoverType: e.target.value }))}
                  className="w-full rounded-xl border border-outline-variant/15 bg-surface-container-high px-3 py-2 text-sm text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                >
                  <option value="">Selecione</option>
                  <option value="hidrogel">Hidrogel</option>
                  <option value="espuma">Espuma</option>
                  <option value="hidrofibra">Hidrofibra</option>
                  <option value="alginato">Alginato</option>
                  <option value="prata_phmb">Prata/PHMB</option>
                </select>
              </div>
              <div className="rounded-xl bg-surface-container p-4 space-y-2">
                <p className="text-xs uppercase tracking-widest text-on-surface-variant">S - Social/Systemic</p>
                <label className="text-xs text-on-surface-variant">Risco de não adesão</label>
                <select
                  value={timersForm.sAdherenceRisk}
                  onChange={(e) => setTimersForm((c) => ({ ...c, sAdherenceRisk: e.target.value }))}
                  className="w-full rounded-xl border border-outline-variant/15 bg-surface-container-high px-3 py-2 text-sm text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                >
                  <option value="">Selecione</option>
                  <option value="baixo">Baixo</option>
                  <option value="moderado">Moderado</option>
                  <option value="alto">Alto</option>
                </select>
                <p className="text-xs text-on-surface-variant pt-1">Barreiras sistêmicas/sociais</p>
                <div className="flex flex-wrap gap-2">
                  {["Dor", "Mobilidade reduzida", "Baixo suporte familiar", "Limitação financeira", "Comorbidades descompensadas"].map(
                    (option) => (
                      <button
                        key={option}
                        type="button"
                        onClick={() => toggleArrayOption("sBarriers", option)}
                        className={`px-2.5 py-1.5 rounded-full text-xs font-semibold transition-colors ${
                          timersForm.sBarriers.includes(option)
                            ? "bg-tertiary/20 text-tertiary"
                            : "bg-surface-container-high text-on-surface-variant hover:text-on-surface"
                        }`}
                      >
                        {option}
                      </button>
                    )
                  )}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-xl bg-surface-container p-4">
                <p className="text-xs uppercase tracking-widest text-on-surface-variant">Paciente</p>
                <p className="text-sm font-semibold mt-1">{selectedPatient?.name ?? "Não selecionado"}</p>
              </div>
              <div className="rounded-xl bg-surface-container p-4">
                <p className="text-xs uppercase tracking-widest text-on-surface-variant">Data</p>
                <p className="text-sm font-semibold mt-1">{evaluationDate}</p>
              </div>
              <div className="rounded-xl bg-surface-container p-4">
                <p className="text-xs uppercase tracking-widest text-on-surface-variant">Tipo de ferida</p>
                <p className="text-sm font-semibold mt-1">{woundTypes.find((item) => item.value === woundType)?.label ?? "Não informado"}</p>
              </div>
            </div>

            <div className="rounded-xl bg-surface-container p-4">
              <p className="text-sm font-bold">Checklist obrigatório</p>
              <ul className="mt-3 space-y-2 text-sm">
                <li className={isStep1Valid ? "text-green-400" : "text-error"}>• Paciente e dados completos</li>
                <li className={isStep2Valid ? "text-green-400" : "text-error"}>• Avaliação clínica e escalas preenchidas</li>
                <li className={isStep3Valid ? "text-green-400" : "text-error"}>• Pelo menos uma foto anexada</li>
                <li className={isStep4Valid ? "text-green-400" : "text-error"}>• TIMERS preenchido (T, I, M, E, R, S)</li>
                <li className={tissueTotalPct === 100 ? "text-green-400" : "text-error"}>• Composição tecidual fechando em 100%</li>
              </ul>
            </div>
          </section>
          )}

          {/* Action Buttons */}
          <div className="flex items-center justify-between pt-4">
            <Button variant="ghost" disabled={currentStep === 1} onClick={handleBack}>
              <span className="material-symbols-outlined text-sm">
                arrow_back
              </span>
              Voltar
            </Button>

            <div className="flex items-center gap-3">
              <Button variant="outline" onClick={saveDraft} disabled={savingDraft}>
                {savingDraft ? "Salvando..." : "Salvar Rascunho"}
              </Button>
              <Button onClick={handleContinue} disabled={!canAdvance || savingEvaluation}>
                {currentStep === 4 ? "Finalizar Avaliação" : "Continuar"}
                <span className="material-symbols-outlined text-sm">
                  arrow_forward
                </span>
              </Button>
            </div>
          </div>
          {statusMessage && (
            <div className="rounded-xl bg-primary/10 text-primary px-4 py-3 text-sm font-medium">
              {statusMessage}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
