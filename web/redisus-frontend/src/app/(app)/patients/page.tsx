"use client";

import { useEffect, useMemo, useState } from "react";
import { jsPDF } from "jspdf";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { Patient } from "@/types/patient";
import {
  createPatient,
  deletePatient,
  listPatients,
  updatePatient,
} from "@/services/firebase/patient-service";

type PatientFormState = {
  id?: string;
  name: string;
  age: string;
  clinicalHistory: string;
};

const emptyForm: PatientFormState = {
  name: "",
  age: "",
  clinicalHistory: "",
};

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

  const refreshPatients = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await listPatients();
      setPatients(data);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Erro ao listar pacientes.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refreshPatients();
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
        age: Number(form.age),
        clinicalHistory: form.clinicalHistory.trim(),
      };

      if (
        !payload.name ||
        !payload.clinicalHistory ||
        Number.isNaN(payload.age)
      ) {
        throw new Error(
          "Preencha nome, idade e histórico clínico corretamente."
        );
      }

      if (isEditing && form.id) {
        await updatePatient(form.id, payload);
      } else {
        await createPatient(payload);
      }

      resetForm();
      await refreshPatients();
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
      await refreshPatients();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Falha ao remover paciente.";
      setError(message);
    }
  };

  const exportCurrentSnapshotPdf = () => {
    const pdf = new jsPDF();
    pdf.setFontSize(16);
    pdf.text("Redisus Heal+ - Snapshot de Pacientes", 14, 20);
    pdf.setFontSize(11);
    pdf.text(`Total filtrado: ${filteredPatients.length}`, 14, 30);

    filteredPatients.slice(0, 20).forEach((patient, index) => {
      const y = 40 + index * 10;
      pdf.text(`${patient.name} | ${patient.age} anos`, 14, y);
    });

    pdf.save("pacientes-healplus.pdf");
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
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-surface-container-low rounded-2xl p-8 w-full max-w-md border border-outline-variant/10 shadow-2xl">
            <div className="flex items-center justify-between mb-6">
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
                  Nome
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

              <div className="space-y-2">
                <label
                  className="text-sm font-medium text-on-surface-variant"
                  htmlFor="patient-age"
                >
                  Idade
                </label>
                <Input
                  id="patient-age"
                  type="number"
                  min={0}
                  placeholder="Idade em anos"
                  value={form.age}
                  onChange={(e) =>
                    setForm((curr) => ({ ...curr, age: e.target.value }))
                  }
                  required
                />
              </div>

              <div className="space-y-2">
                <label
                  className="text-sm font-medium text-on-surface-variant"
                  htmlFor="patient-history"
                >
                  Histórico Clínico
                </label>
                <Textarea
                  id="patient-history"
                  rows={4}
                  placeholder="Descreva o histórico clínico do paciente..."
                  value={form.clinicalHistory}
                  onChange={(e) =>
                    setForm((curr) => ({
                      ...curr,
                      clinicalHistory: e.target.value,
                    }))
                  }
                  required
                />
              </div>

              <div className="flex gap-3 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  className="flex-1"
                  onClick={resetForm}
                >
                  Cancelar
                </Button>
                <Button type="submit" className="flex-1" disabled={saving}>
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
                        {patient.age} anos
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
                          age: String(patient.age),
                          clinicalHistory: patient.clinicalHistory,
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
