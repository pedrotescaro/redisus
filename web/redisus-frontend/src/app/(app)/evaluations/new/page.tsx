"use client";

import { useState, useRef } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";

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

export default function NewEvaluationPage() {
  const [currentStep, setCurrentStep] = useState(1);
  const [patientSearch, setPatientSearch] = useState("");
  const [evaluationDate, setEvaluationDate] = useState(
    new Date().toISOString().split("T")[0]
  );
  const [woundType, setWoundType] = useState("");
  const [clinicalDescription, setClinicalDescription] = useState("");
  const [photoSlots, setPhotoSlots] = useState<PhotoSlot[]>([
    { id: "frontal", label: "Foto Frontal", file: null, preview: null },
    { id: "lateral", label: "Foto Lateral", file: null, preview: null },
    { id: "detail", label: "Foto Detalhe", file: null, preview: null },
  ]);

  const fileInputRefs = useRef<{ [key: string]: HTMLInputElement | null }>({});

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
      title: "Descrição da Ferida",
      status:
        currentStep === 2
          ? "in_progress"
          : currentStep > 2
            ? "completed"
            : "pending",
    },
    {
      id: 3,
      title: "Upload de Imagens",
      status:
        currentStep === 3
          ? "in_progress"
          : currentStep > 3
            ? "completed"
            : "pending",
    },
    {
      id: 4,
      title: "Conclusão",
      status: currentStep === 4 ? "in_progress" : "pending",
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
          Protocolo v2.4 Ativo
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
          {/* Section: Identification */}
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
              <div className="space-y-2">
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

          {/* Section: Photo Upload */}
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
          </section>

          {/* Action Buttons */}
          <div className="flex items-center justify-between pt-4">
            <Button variant="ghost" disabled={currentStep === 1}>
              <span className="material-symbols-outlined text-sm">
                arrow_back
              </span>
              Voltar
            </Button>

            <div className="flex items-center gap-3">
              <Button variant="outline">Salvar Rascunho</Button>
              <Button>
                {currentStep === 4 ? "Finalizar Avaliação" : "Continuar"}
                <span className="material-symbols-outlined text-sm">
                  arrow_forward
                </span>
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
