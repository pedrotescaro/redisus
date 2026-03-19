"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { Patient } from "@/types/patient";
import {
  createPatient,
  deletePatient,
  listPatients,
  primePatientsCache,
  updatePatient,
} from "@/services/firebase/patient-service";

type PatientFormState = {
  id?: string;
  name: string;
  birthDate: string;
  phone: string;
  email: string;
  profession: string;
  maritalStatus: string;
  clinicalHistory: string;
  hppItems: string[];
  comorbidities: string[];
  medicationsInUse: Array<{
    name: string;
    dose: string;
  }>;
};

const emptyForm: PatientFormState = {
  name: "",
  birthDate: "",
  phone: "",
  email: "",
  profession: "",
  maritalStatus: "",
  clinicalHistory: "",
  hppItems: [],
  comorbidities: [],
  medicationsInUse: [{ name: "", dose: "" }],
};
const PATIENTS_STORAGE_KEY = "healplus-patients-cache";
const MARITAL_STATUS_OPTIONS = [
  "Solteiro(a)",
  "Casado(a)",
  "União estável",
  "Divorciado(a)",
  "Viúvo(a)",
  "Prefiro não informar",
];
const HPP_OPTIONS = [
  "Hipertensão arterial",
  "Diabetes mellitus",
  "Doença vascular periférica",
  "Insuficiência venosa crônica",
  "Tabagismo",
  "Etilismo",
  "Histórico de amputação",
];
const COMORBIDITY_OPTIONS = [
  "Obesidade",
  "Doença renal crônica",
  "Insuficiência cardíaca",
  "Neuropatia periférica",
  "Doença arterial coronariana",
  "Imunossupressão",
  "Doença pulmonar crônica",
];

function getAgeFromBirthDate(birthDate: string) {
  if (!birthDate) return null;
  const birth = new Date(`${birthDate}T12:00:00`);
  if (Number.isNaN(birth.getTime())) return null;

  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const hasNotHadBirthdayYet =
    today.getMonth() < birth.getMonth() ||
    (today.getMonth() === birth.getMonth() &&
      today.getDate() < birth.getDate());
  if (hasNotHadBirthdayYet) age -= 1;
  return age >= 0 ? age : null;
}

function toggleOption(list: string[], option: string) {
  return list.includes(option)
    ? list.filter((item) => item !== option)
    : [...list, option];
}

function buildClinicalHistorySummary(form: PatientFormState) {
  const hpp =
    form.hppItems.length > 0 ? `HPP: ${form.hppItems.join(", ")}.` : "HPP: não informado.";
  const comorb =
    form.comorbidities.length > 0
      ? `Comorbidades: ${form.comorbidities.join(", ")}.`
      : "Comorbidades: não informado.";
  const meds = form.medicationsInUse
    .filter((m) => m.name.trim() && m.dose.trim())
    .map((m) => `${m.name.trim()} (${m.dose.trim()})`);
  const medsText =
    meds.length > 0
      ? `Medicamentos em uso: ${meds.join(", ")}.`
      : "Medicamentos em uso: não informado.";
  const note = form.clinicalHistory.trim()
    ? `Observações clínicas: ${form.clinicalHistory.trim()}`
    : "";
  return [hpp, comorb, medsText, note].filter(Boolean).join(" ");
}

function sortPatientsByName(data: Patient[]) {
  return [...data].sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));
}

export default function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<PatientFormState>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const isEditing = Boolean(form.id);

  const filteredPatients = useMemo(() => {
    const normalized = search.trim().toLowerCase();

    if (!normalized) {
      return patients;
    }

    return patients.filter((patient) => {
      return (
        patient.name.toLowerCase().includes(normalized) ||
        patient.clinicalHistory.toLowerCase().includes(normalized)
      );
    });
  }, [patients, search]);

  const syncLocalPatientsCache = (data: Patient[]) => {
    if (typeof window === "undefined") return;
    sessionStorage.setItem(PATIENTS_STORAGE_KEY, JSON.stringify(data));
    primePatientsCache(data);
  };

  const refreshPatients = async (options?: { forceRefresh?: boolean; keepCurrentUI?: boolean }) => {
    if (!options?.keepCurrentUI) {
      setLoading(true);
    }
    setError(null);

    try {
      const data = await listPatients({ forceRefresh: options?.forceRefresh });
      setPatients(data);
      syncLocalPatientsCache(data);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Erro ao listar pacientes.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (typeof window !== "undefined") {
      const cachedRaw = sessionStorage.getItem(PATIENTS_STORAGE_KEY);
      if (cachedRaw) {
        try {
          const cached = JSON.parse(cachedRaw) as Patient[];
          if (Array.isArray(cached) && cached.length > 0) {
            const sorted = sortPatientsByName(cached);
            setPatients(sorted);
            setLoading(false);
            primePatientsCache(sorted);
          }
        } catch {
          sessionStorage.removeItem(PATIENTS_STORAGE_KEY);
        }
      }
    }

    void refreshPatients({ keepCurrentUI: true });
  }, []);

  const resetForm = () => {
    setForm(emptyForm);
    setShowForm(false);
  };

  const handleSavePatient = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError(null);

    try {
      const payload = {
        name: form.name.trim(),
        birthDate: form.birthDate,
        phone: form.phone.trim(),
        email: form.email.trim().toLowerCase(),
        profession: form.profession.trim(),
        maritalStatus: form.maritalStatus.trim(),
        age: getAgeFromBirthDate(form.birthDate) ?? undefined,
        hppItems: form.hppItems,
        comorbidities: form.comorbidities,
        medicationsInUse: form.medicationsInUse.filter(
          (item) => item.name.trim() && item.dose.trim()
        ),
        clinicalHistory: buildClinicalHistorySummary(form),
      };

      if (
        !payload.name ||
        !payload.birthDate ||
        !payload.phone ||
        !payload.email ||
        !payload.profession ||
        !payload.maritalStatus ||
        !payload.email.includes("@")
      ) {
        throw new Error(
          "Preencha nome, data de nascimento, telefone, e-mail, profissão e estado civil."
        );
      }

      if (isEditing && form.id) {
        await updatePatient(form.id, payload);
        setPatients((current) => {
          const next = sortPatientsByName(
            current.map((patient) =>
              patient.id === form.id
                ? {
                    ...patient,
                    ...payload,
                  }
                : patient
            )
          );
          syncLocalPatientsCache(next);
          return next;
        });
      } else {
        const created = await createPatient(payload);
        setPatients((current) => {
          const next = sortPatientsByName([
            ...current,
            {
              id: created.id,
              ...payload,
            } as Patient,
          ]);
          syncLocalPatientsCache(next);
          return next;
        });
      }

      resetForm();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Falha ao salvar paciente.";
      setError(message);
    } finally {
      setSaving(false);
    }
  };

  const handleDeletePatient = async (id: string) => {
    const confirmation = window.confirm("Deseja remover este paciente?");

    if (!confirmation) {
      return;
    }

    try {
      await deletePatient(id);
      setPatients((current) => {
        const next = current.filter((patient) => patient.id !== id);
        syncLocalPatientsCache(next);
        return next;
      });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Falha ao remover paciente.";
      setError(message);
    }
  };

  const exportCurrentSnapshotPdf = () => {
    void (async () => {
      const { jsPDF } = await import("jspdf");
      const pdf = new jsPDF();
      pdf.setFontSize(16);
      pdf.text("Redisus Heal+ - Snapshot de Pacientes", 14, 20);
      pdf.setFontSize(11);
      pdf.text(`Total filtrado: ${filteredPatients.length}`, 14, 30);

      filteredPatients.slice(0, 20).forEach((patient, index) => {
        const y = 40 + index * 10;
        const derivedAge = patient.age ?? getAgeFromBirthDate(patient.birthDate);
        pdf.text(
          `${patient.name} | ${derivedAge ?? "-"} anos | ${patient.phone}`,
          14,
          y
        );
      });

      pdf.save("pacientes-healplus.pdf");
    })();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold font-headline text-on-surface">
            Pacientes
          </h1>
          <p className="text-on-surface-variant mt-1">
            Gerencie seus pacientes e históricos clínicos
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={exportCurrentSnapshotPdf}>
            <span className="material-symbols-outlined text-sm">
              download
            </span>
            Exportar PDF
          </Button>
          <Button onClick={() => setShowForm(true)}>
            <span className="material-symbols-outlined text-sm">add</span>
            Novo Paciente
          </Button>
        </div>
      </div>

      {/* Search Bar */}
      <div className="flex items-center bg-surface-container-high/50 rounded-xl px-4 py-1.5 max-w-md focus-within:ring-2 focus-within:ring-primary/50 transition-all">
        <span className="material-symbols-outlined text-gray-400 text-lg mr-2">
          search
        </span>
        <input
          type="text"
          className="bg-transparent border-none focus:ring-0 focus:outline-none text-sm w-full text-on-surface placeholder:text-gray-500 font-body py-2"
          placeholder="Buscar por nome ou histórico clínico..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Error Alert */}
      {error && (
        <div className="rounded-xl border border-error/30 bg-error-container/20 px-4 py-3 text-sm text-error flex items-center gap-2">
          <span className="material-symbols-outlined text-sm">error</span>
          {error}
        </div>
      )}

      {/* Patient Form Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-2 sm:p-4">
          <div className="bg-surface-container-low rounded-2xl p-4 sm:p-6 lg:p-8 w-full max-w-3xl max-h-[92vh] overflow-y-auto border border-outline-variant/10 shadow-2xl">
            <div className="flex items-center justify-between mb-6 sticky top-0 z-10 bg-surface-container-low py-1">
              <h2 className="text-xl font-bold font-headline text-on-surface">
                {isEditing ? "Editar Paciente" : "Novo Paciente"}
              </h2>
              <button
                onClick={resetForm}
                className="p-2 hover:bg-surface-container-high rounded-full transition-colors"
              >
                <span className="material-symbols-outlined text-gray-400">
                  close
                </span>
              </button>
            </div>

            <form className="space-y-4" onSubmit={handleSavePatient}>
              <div className="space-y-2">
                <label
                  className="text-sm font-medium text-on-surface-variant"
                  htmlFor="patient-name"
                >
                  Nome completo
                </label>
                <Input
                  id="patient-name"
                  placeholder="Nome completo do paciente"
                  value={form.name}
                  onChange={(e) =>
                    setForm((curr) => ({ ...curr, name: e.target.value }))
                  }
                  required
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label
                    className="text-sm font-medium text-on-surface-variant"
                    htmlFor="patient-birth-date"
                  >
                    Data de nascimento
                  </label>
                  <Input
                    id="patient-birth-date"
                    type="date"
                    value={form.birthDate}
                    onChange={(e) =>
                      setForm((curr) => ({ ...curr, birthDate: e.target.value }))
                    }
                    required
                  />
                </div>
                <div className="space-y-2">
                  <label
                    className="text-sm font-medium text-on-surface-variant"
                    htmlFor="patient-phone"
                  >
                    Telefone
                  </label>
                  <Input
                    id="patient-phone"
                    placeholder="(11) 99999-9999"
                    value={form.phone}
                    onChange={(e) =>
                      setForm((curr) => ({ ...curr, phone: e.target.value }))
                    }
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label
                    className="text-sm font-medium text-on-surface-variant"
                    htmlFor="patient-email"
                  >
                    E-mail
                  </label>
                  <Input
                    id="patient-email"
                    type="email"
                    placeholder="nome@dominio.com"
                    value={form.email}
                    onChange={(e) =>
                      setForm((curr) => ({ ...curr, email: e.target.value }))
                    }
                    required
                  />
                </div>
                <div className="space-y-2">
                  <label
                    className="text-sm font-medium text-on-surface-variant"
                    htmlFor="patient-profession"
                  >
                    Profissão
                  </label>
                  <Input
                    id="patient-profession"
                    placeholder="Profissão"
                    value={form.profession}
                    onChange={(e) =>
                      setForm((curr) => ({ ...curr, profession: e.target.value }))
                    }
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label
                  className="text-sm font-medium text-on-surface-variant"
                  htmlFor="patient-marital-status"
                >
                  Estado civil
                </label>
                <select
                  id="patient-marital-status"
                  value={form.maritalStatus}
                  onChange={(e) =>
                    setForm((curr) => ({
                      ...curr,
                      maritalStatus: e.target.value,
                    }))
                  }
                  className="w-full rounded-xl border border-outline-variant/20 bg-surface-container-high px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/50"
                  required
                >
                  <option value="">Selecione</option>
                  {MARITAL_STATUS_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <label
                  className="text-sm font-medium text-on-surface-variant"
                  htmlFor="patient-history"
                >
                  Observações clínicas adicionais
                </label>
                <Textarea
                  id="patient-history"
                  rows={3}
                  placeholder="Campo livre opcional para observações..."
                  value={form.clinicalHistory}
                  onChange={(e) =>
                    setForm((curr) => ({
                      ...curr,
                      clinicalHistory: e.target.value,
                    }))
                  }
                />
              </div>

              <div className="space-y-3">
                <label className="text-sm font-medium text-on-surface-variant">
                  HPP (História Patológica Pregressa)
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {HPP_OPTIONS.map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() =>
                        setForm((curr) => ({
                          ...curr,
                          hppItems: toggleOption(curr.hppItems, option),
                        }))
                      }
                      className={`px-3 py-2 rounded-xl text-xs text-left font-semibold transition-colors ${
                        form.hppItems.includes(option)
                          ? "bg-primary/20 text-primary"
                          : "bg-surface-container-high text-on-surface-variant hover:text-on-surface"
                      }`}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <label className="text-sm font-medium text-on-surface-variant">
                  Comorbidades
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {COMORBIDITY_OPTIONS.map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() =>
                        setForm((curr) => ({
                          ...curr,
                          comorbidities: toggleOption(curr.comorbidities, option),
                        }))
                      }
                      className={`px-3 py-2 rounded-xl text-xs text-left font-semibold transition-colors ${
                        form.comorbidities.includes(option)
                          ? "bg-tertiary/20 text-tertiary"
                          : "bg-surface-container-high text-on-surface-variant hover:text-on-surface"
                      }`}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-on-surface-variant">
                    Medicamentos em uso (nome e dose)
                  </label>
                  <button
                    type="button"
                    onClick={() =>
                      setForm((curr) => ({
                        ...curr,
                        medicationsInUse: [...curr.medicationsInUse, { name: "", dose: "" }],
                      }))
                    }
                    className="text-xs font-bold text-primary hover:underline"
                  >
                    + Adicionar medicamento
                  </button>
                </div>
                <div className="space-y-2">
                  {form.medicationsInUse.map((medication, index) => (
                    <div key={`med-${index}`} className="grid grid-cols-1 lg:grid-cols-[1fr_220px_auto] gap-2 items-center">
                      <Input
                        placeholder="Nome do medicamento"
                        value={medication.name}
                        onChange={(e) =>
                          setForm((curr) => ({
                            ...curr,
                            medicationsInUse: curr.medicationsInUse.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, name: e.target.value } : item
                            ),
                          }))
                        }
                      />
                      <Input
                        placeholder="Dose (ex: 500mg 8/8h)"
                        value={medication.dose}
                        onChange={(e) =>
                          setForm((curr) => ({
                            ...curr,
                            medicationsInUse: curr.medicationsInUse.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, dose: e.target.value } : item
                            ),
                          }))
                        }
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setForm((curr) => ({
                            ...curr,
                            medicationsInUse:
                              curr.medicationsInUse.length === 1
                                ? [{ name: "", dose: "" }]
                                : curr.medicationsInUse.filter((_, itemIndex) => itemIndex !== index),
                          }))
                        }
                        className="p-2 rounded-lg hover:bg-error/10 text-error"
                        aria-label="Remover medicamento"
                      >
                        <span className="material-symbols-outlined text-sm">delete</span>
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex flex-col-reverse sm:flex-row gap-3 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  className="w-full sm:flex-1"
                  onClick={resetForm}
                >
                  Cancelar
                </Button>
                <Button type="submit" className="w-full sm:flex-1" disabled={saving}>
                  {saving
                    ? "Salvando..."
                    : isEditing
                      ? "Salvar Alterações"
                      : "Adicionar Paciente"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Patients List */}
      <div className="bg-surface-container-low rounded-xl border border-outline-variant/5 overflow-hidden">
        {loading ? (
          <div className="p-12 text-center">
            <div className="w-10 h-10 rounded-full border-2 border-primary-container border-t-transparent animate-spin mx-auto mb-4"></div>
            <p className="text-on-surface-variant">Carregando pacientes...</p>
          </div>
        ) : filteredPatients.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-16 h-16 bg-surface-container-high rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="material-symbols-outlined text-3xl text-gray-600">
                person_off
              </span>
            </div>
            <h3 className="text-lg font-bold font-headline text-on-surface mb-2">
              Nenhum paciente encontrado
            </h3>
            <p className="text-on-surface-variant text-sm mb-4">
              {search
                ? "Tente ajustar sua busca"
                : "Comece adicionando seu primeiro paciente"}
            </p>
            {!search && (
              <Button onClick={() => setShowForm(true)}>
                <span className="material-symbols-outlined text-sm">add</span>
                Adicionar Paciente
              </Button>
            )}
          </div>
        ) : (
          <div className="divide-y divide-outline-variant/10">
            {filteredPatients.map((patient) => (
              <div
                key={patient.id}
                className="p-6 hover:bg-surface-container transition-colors group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary flex-shrink-0">
                      <span className="material-symbols-outlined">person</span>
                    </div>
                    <div>
                      <h3 className="text-lg font-bold font-headline text-on-surface">
                        {patient.name}
                      </h3>
                      <p className="text-sm text-on-surface-variant mt-0.5">
                        {patient.age ?? getAgeFromBirthDate(patient.birthDate) ?? "-"} anos
                      </p>
                      <p className="text-xs text-on-surface-variant mt-1">
                        {patient.phone} • {patient.email}
                      </p>
                      <p className="text-xs text-on-surface-variant mt-1">
                        {patient.profession} • {patient.maritalStatus}
                      </p>
                      <p className="text-sm text-gray-500 mt-2 line-clamp-2">
                        {patient.clinicalHistory}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                      variant="ghost"
                      onClick={() => {
                        setForm({
                          id: patient.id,
                          name: patient.name,
                          birthDate: patient.birthDate ?? "",
                          phone: patient.phone ?? "",
                          email: patient.email ?? "",
                          profession: patient.profession ?? "",
                          maritalStatus: patient.maritalStatus ?? "",
                          clinicalHistory: patient.clinicalHistory,
                          hppItems: patient.hppItems ?? [],
                          comorbidities: patient.comorbidities ?? [],
                          medicationsInUse:
                            patient.medicationsInUse && patient.medicationsInUse.length > 0
                              ? patient.medicationsInUse
                              : [{ name: "", dose: "" }],
                        });
                        setShowForm(true);
                      }}
                    >
                      <span className="material-symbols-outlined text-sm">
                        edit
                      </span>
                      Editar
                    </Button>
                    <Button
                      variant="outline"
                      className="text-error hover:bg-error/10 hover:border-error/30"
                      onClick={() => void handleDeletePatient(patient.id)}
                    >
                      <span className="material-symbols-outlined text-sm">
                        delete
                      </span>
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
