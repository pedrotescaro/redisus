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

export function PatientDashboard() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<PatientFormState>(emptyForm);
  const [saving, setSaving] = useState(false);

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
      const message = err instanceof Error ? err.message : "Erro ao listar pacientes.";
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

      if (!payload.name || !payload.clinicalHistory || Number.isNaN(payload.age)) {
        throw new Error("Preencha nome, idade e historico clinico corretamente.");
      }

      if (isEditing && form.id) {
        await updatePatient(form.id, payload);
      } else {
        await createPatient(payload);
      }

      resetForm();
      await refreshPatients();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Falha ao salvar paciente.";
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
      const message = err instanceof Error ? err.message : "Falha ao remover paciente.";
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
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
      <section className="rounded-2xl bg-white p-6 shadow-soft">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-brand-600">Dashboard de Pacientes</p>
            <h1 className="text-2xl font-semibold text-brand-900">Gestao clinica ativa</h1>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={exportCurrentSnapshotPdf}>
              Exportar PDF
            </Button>
            <Button variant="ghost" onClick={() => void refreshPatients()}>
              Atualizar
            </Button>
          </div>
        </div>

        <div className="mt-6">
          <label className="mb-2 block text-sm font-medium text-slate-700" htmlFor="search-patient">
            Buscar paciente
          </label>
          <Input
            id="search-patient"
            placeholder="Nome ou historico clinico"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>

        {error && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
        )}

        <div className="mt-6 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="border-b border-brand-100 text-slate-600">
                <th className="pb-3 pr-4 font-medium">Paciente</th>
                <th className="pb-3 pr-4 font-medium">Idade</th>
                <th className="pb-3 pr-4 font-medium">Historico clinico</th>
                <th className="pb-3 text-right font-medium">Acoes</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td className="py-4 text-slate-500" colSpan={4}>
                    Carregando pacientes...
                  </td>
                </tr>
              ) : filteredPatients.length === 0 ? (
                <tr>
                  <td className="py-4 text-slate-500" colSpan={4}>
                    Nenhum paciente encontrado.
                  </td>
                </tr>
              ) : (
                filteredPatients.map((patient) => (
                  <tr key={patient.id} className="border-b border-slate-100 align-top">
                    <td className="py-4 pr-4 font-medium text-slate-800">{patient.name}</td>
                    <td className="py-4 pr-4 text-slate-700">{patient.age}</td>
                    <td className="py-4 pr-4 text-slate-700">{patient.clinicalHistory}</td>
                    <td className="py-4 text-right">
                      <div className="inline-flex gap-1">
                        <Button
                          variant="ghost"
                          onClick={() => {
                            setForm({
                              id: patient.id,
                              name: patient.name,
                              age: String(patient.age),
                              clinicalHistory: patient.clinicalHistory,
                            });
                          }}
                        >
                          Editar
                        </Button>
                        <Button variant="danger" onClick={() => void handleDeletePatient(patient.id)}>
                          Remover
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="h-fit rounded-2xl bg-white p-6 shadow-soft">
        <h2 className="text-lg font-semibold text-brand-900">{isEditing ? "Editar paciente" : "Novo paciente"}</h2>
        <p className="mt-1 text-sm text-slate-600">Cadastro rapido com historico clinico basico.</p>

        <form className="mt-5 space-y-4" onSubmit={handleSavePatient}>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="patient-name">
              Nome
            </label>
            <Input
              id="patient-name"
              value={form.name}
              onChange={(event) => setForm((curr) => ({ ...curr, name: event.target.value }))}
              required
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="patient-age">
              Idade
            </label>
            <Input
              id="patient-age"
              type="number"
              min={0}
              value={form.age}
              onChange={(event) => setForm((curr) => ({ ...curr, age: event.target.value }))}
              required
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="patient-history">
              Historico clinico basico
            </label>
            <Textarea
              id="patient-history"
              rows={4}
              value={form.clinicalHistory}
              onChange={(event) => setForm((curr) => ({ ...curr, clinicalHistory: event.target.value }))}
              required
            />
          </div>

          <div className="flex gap-2">
            <Button type="submit" disabled={saving}>
              {saving ? "Salvando..." : isEditing ? "Salvar alteracoes" : "Adicionar paciente"}
            </Button>
            {isEditing && (
              <Button type="button" variant="secondary" onClick={resetForm}>
                Cancelar
              </Button>
            )}
          </div>
        </form>
      </section>
    </div>
  );
}
