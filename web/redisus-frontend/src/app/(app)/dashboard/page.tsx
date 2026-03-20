"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { onAuthStateChanged, type User } from "firebase/auth";
import {
  collection,
  getDocs,
  query,
  where,
  orderBy,
  limit,
  Timestamp,
} from "firebase/firestore";
import { auth, db } from "@/lib/firebase";
import { listPatients } from "@/services/firebase/patient-service";
import type { Patient } from "@/types/patient";

export default function DashboardPage() {
  const [user, setUser] = useState<User | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [recentEvalCount, setRecentEvalCount] = useState<number | null>(null);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (authUser) => {
      setUser(authUser);
    });
    return () => unsubscribe();
  }, []);

  useEffect(() => {
    async function fetchPatients() {
      try {
        const data = await listPatients();
        setPatients(data);
      } catch {
        // Handle error silently
      } finally {
        setLoading(false);
      }
    }
    void fetchPatients();
  }, []);

  // Fetch recent evaluations count from Firestore
  useEffect(() => {
    if (!user) return;
    let active = true;
    void (async () => {
      try {
        const sevenDaysAgo = new Date();
        sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
        const evalsRef = collection(db, "clinical_evaluations");
        const q = query(
          evalsRef,
          where("uid", "==", user.uid),
          where("createdAt", ">=", Timestamp.fromDate(sevenDaysAgo)),
          orderBy("createdAt", "desc"),
          limit(100),
        );
        const snapshot = await getDocs(q);
        if (active) setRecentEvalCount(snapshot.size);
      } catch {
        if (active) setRecentEvalCount(0);
      }
    })();
    return () => { active = false; };
  }, [user]);

  const userName =
    user?.displayName || user?.email?.split("@")[0] || "Profissional";

  const today = new Date();
  const formattedDate = today.toLocaleDateString("pt-BR", {
    day: "numeric",
    month: "long",
  });

  return (
    <div className="space-y-8">
      {/* Greeting Hero Section */}
      <section className="relative overflow-hidden rounded-xl bg-surface-container-lowest p-10 shadow-ambient">
        <div className="relative z-10 max-w-2xl">
          <p className="text-2xl font-semibold font-nav text-on-surface tracking-tight mb-2">
            Olá, {userName}.
          </p>
          <h2 className="text-4xl font-extrabold font-nav text-primary tracking-tight mb-4">
            Sua central de gestão inteligente de feridas.
          </h2>
          <p className="text-on-surface-variant font-body leading-relaxed mb-6">
            Acompanhe a evolução clínica, analise métricas de cicatrização e
            gere laudos detalhados com inteligência artificial em poucos
            cliques.
          </p>
          <Link
            href="/evaluations/new"
            className="bg-primary-gradient text-white px-6 py-3 rounded-lg font-bold flex items-center gap-2 hover:opacity-90 transition-opacity shadow-ambient w-fit"
          >
            <span className="material-symbols-outlined">add_circle</span>
            Iniciar Nova Avaliação
          </Link>
        </div>

        {/* Abstract visual elements */}
        <div className="absolute -right-20 -top-20 w-96 h-96 bg-primary/10 rounded-full blur-[100px]"></div>
        <div className="absolute right-12 bottom-0 opacity-10 pointer-events-none">
          <span className="material-symbols-outlined text-[240px] text-primary">
            medical_services
          </span>
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Case Evolution Stats */}
        <div className="lg:col-span-2 space-y-6">
          <div className="flex justify-between items-end">
            <h3 className="text-xl font-bold font-headline text-on-surface">
              Evolução de casos
            </h3>
            <Link
              href="/reports"
              className="text-sm text-primary font-semibold hover:underline"
            >
              Ver relatório completo
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Stat Card 1 - Active Patients */}
            <div className="bg-surface-container-lowest p-8 rounded-xl shadow-ambient border border-transparent hover:border-outline-variant/20 transition-all group">
              <div className="flex justify-between items-start mb-6">
                <div className="bg-primary/10 p-3 rounded-xl text-primary group-hover:scale-110 transition-transform">
                  <span className="material-symbols-outlined text-3xl">
                    personal_injury
                  </span>
                </div>
                <span className="text-[10px] font-bold text-on-surface-variant bg-surface-container px-3 py-1 rounded-full uppercase tracking-tight">
                  Hoje
                </span>
              </div>
              <div className="space-y-1">
                <p className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-1">
                  Pacientes Ativos
                </p>
                <div className="flex items-baseline gap-2">
                  <h4 className="text-6xl font-bold font-headline text-on-surface">
                    {loading ? "-" : patients.length}
                  </h4>
                  <span className="text-sm font-medium text-on-surface-variant">
                    em tratamento
                  </span>
                </div>
              </div>
              <div className="mt-8 h-1 w-full bg-surface-container rounded-full overflow-hidden">
                <div className="h-full bg-primary-container w-0 transition-all duration-1000"></div>
              </div>
            </div>

            {/* Stat Card 2 - Recent Evaluations (real data from Firestore) */}
            <div className="bg-surface-container-lowest p-8 rounded-xl shadow-ambient border border-transparent hover:border-outline-variant/20 transition-all group">
              <div className="flex justify-between items-start mb-6">
                <div className="bg-primary/10 p-3 rounded-xl text-primary group-hover:scale-110 transition-transform">
                  <span className="material-symbols-outlined text-3xl">
                    assignment_add
                  </span>
                </div>
                <span className="text-[10px] font-bold text-on-surface-variant bg-surface-container px-3 py-1 rounded-full uppercase tracking-tight">
                  Últimos 7 dias
                </span>
              </div>
              <div className="space-y-1">
                <p className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-1">
                  Avaliações Recentes
                </p>
                <div className="flex items-baseline gap-2">
                  <h4 className="text-6xl font-bold font-headline text-on-surface">
                    {recentEvalCount === null ? "-" : recentEvalCount}
                  </h4>
                  <span className="text-sm font-medium text-on-surface-variant">
                    realizadas
                  </span>
                </div>
              </div>
              <div className="mt-8 flex gap-1">
                <div className="h-1 flex-1 bg-primary-container rounded-full"></div>
                <div className="h-1 flex-1 bg-primary-container rounded-full"></div>
                <div className="h-1 flex-1 bg-primary-container rounded-full"></div>
                <div className="h-1 flex-1 bg-primary-container rounded-full"></div>
                <div className="h-1 flex-1 bg-surface-container rounded-full"></div>
              </div>
            </div>
          </div>
        </div>

        {/* Quick Shortcuts */}
        <div className="space-y-6">
          <h3 className="text-xl font-bold font-headline text-on-surface">Atalhos Rápidos</h3>

          <div className="grid grid-cols-2 gap-4">
            {/* Shortcut 1 - New Evaluation */}
            <Link
              href="/evaluations/new"
              className="flex flex-col items-start gap-4 p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/10 hover:border-primary/30 transition-all group"
            >
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center text-primary group-hover:bg-primary group-hover:text-white transition-colors">
                <span className="material-symbols-outlined">add_circle</span>
              </div>
              <span className="text-sm font-bold text-on-surface">
                Nova Avaliação
              </span>
            </Link>

            {/* Shortcut 2 - Generate Report */}
            <Link
              href="/reports"
              className="flex flex-col items-start gap-4 p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/10 hover:border-primary/30 transition-all group"
            >
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center text-primary group-hover:bg-primary group-hover:text-white transition-colors">
                <span className="material-symbols-outlined">analytics</span>
              </div>
              <span className="text-sm font-bold text-on-surface">
                Gerar Relatório
              </span>
            </Link>

            {/* Shortcut 3 - Patients */}
            <Link
              href="/patients"
              className="flex flex-col items-start gap-4 p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/10 hover:border-primary/30 transition-all group"
            >
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center text-primary group-hover:bg-primary group-hover:text-white transition-colors">
                <span className="material-symbols-outlined">groups</span>
              </div>
              <span className="text-sm font-bold text-on-surface">Pacientes</span>
            </Link>

            {/* Shortcut 4 - Compare */}
            <Link
              href="/comparison"
              className="flex flex-col items-start gap-4 p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/10 hover:border-primary/30 transition-all group"
            >
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center text-primary group-hover:bg-primary group-hover:text-white transition-colors">
                <span className="material-symbols-outlined">compare</span>
              </div>
              <span className="text-sm font-bold text-on-surface">Comparar</span>
            </Link>
          </div>

          {/* Calendar Mini-View */}
          <div className="bg-surface-container-lowest rounded-xl p-6 shadow-ambient">
            <div className="flex items-center justify-between mb-8">
              <h4 className="text-lg font-bold text-on-surface">
                Próximos Agendamentos
              </h4>
              <span className="material-symbols-outlined text-on-surface-variant cursor-pointer hover:text-on-surface">
                more_horiz
              </span>
            </div>
            {/* Empty State Schedule */}
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <div className="w-24 h-24 bg-surface-container-low rounded-full flex items-center justify-center mb-4">
                <span className="material-symbols-outlined text-4xl text-outline-variant" style={{ fontVariationSettings: "'wght' 200" }}>
                  event_busy
                </span>
              </div>
              <p className="text-on-surface font-bold mb-1">Sem pacientes agendados</p>
              <p className="text-on-surface-variant text-sm">Hoje, {formattedDate}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Section: Status Card */}
      <section className="bg-primary-gradient rounded-xl p-6 text-white">
        <div className="flex items-center gap-4 mb-4">
          <span className="material-symbols-outlined text-3xl">verified</span>
          <div>
            <p className="font-bold text-lg">Tudo em ordem por aqui</p>
            <p className="text-white/80 text-xs">Seu sistema está atualizado e sincronizado.</p>
          </div>
        </div>
        <hr className="border-white/20 mb-4" />
        <button className="text-white text-sm font-bold flex items-center justify-between group w-full">
          Saiba como começar
          <span className="material-symbols-outlined group-hover:translate-x-1 transition-transform">chevron_right</span>
        </button>
      </section>
    </div>
  );
}
