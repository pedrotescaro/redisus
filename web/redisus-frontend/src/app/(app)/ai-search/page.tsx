"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { onAuthStateChanged, type User } from "firebase/auth";
import { auth } from "@/lib/firebase";

type QuickSuggestion = {
  id: string;
  text: string;
  icon: string;
};

type RecentInteraction = {
  id: string;
  icon: string;
  iconBg: string;
  iconColor: string;
  title: string;
  description: string;
  time: string;
};

type Tutorial = {
  id: string;
  icon: string;
  title: string;
  description: string;
  badge?: string;
  action?: {
    label: string;
    variant: "primary" | "outline";
  };
};

const quickSuggestions: QuickSuggestion[] = [
  { id: "1", text: "Buscar histórico de Maria Silva", icon: "history" },
  { id: "2", text: "Gerar relatório de evolução semanal", icon: "description" },
  { id: "3", text: "Como registrar uma nova ferida?", icon: "help" },
  { id: "4", text: "Pacientes com cicatrização atrasada", icon: "warning" },
];

const recentInteractions: RecentInteraction[] = [
  {
    id: "1",
    icon: "analytics",
    iconBg: "bg-primary/10",
    iconColor: "text-primary",
    title: "Análise de cicatrização",
    description: "Relatório gerado para João Pereira",
    time: "Há 2 horas",
  },
  {
    id: "2",
    icon: "person_search",
    iconBg: "bg-tertiary/10",
    iconColor: "text-tertiary",
    title: "Busca de paciente",
    description: '"Ana Costa" - 3 resultados encontrados',
    time: "Ontem",
  },
  {
    id: "3",
    icon: "help_outline",
    iconBg: "bg-secondary/10",
    iconColor: "text-secondary",
    title: "Pergunta respondida",
    description: "Como exportar relatórios em PDF?",
    time: "2 dias atrás",
  },
];

const tutorials: Tutorial[] = [
  {
    id: "1",
    icon: "add_a_photo",
    title: "Upload de Fotos",
    description: "Aprenda a capturar e enviar fotos de feridas corretamente.",
  },
  {
    id: "2",
    icon: "speed",
    title: "Análise Clínica Rápida",
    description: "Entenda como a IA processa e analisa as imagens.",
  },
  {
    id: "3",
    icon: "school",
    title: "Workshop Heal+",
    description: "Participe do nosso workshop online ao vivo.",
    badge: "AO VIVO",
    action: {
      label: "Inscrever-se",
      variant: "primary",
    },
  },
];

export default function AISearchPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (authUser) => {
      setUser(authUser);
    });
    return () => unsubscribe();
  }, []);

  const userName =
    user?.displayName?.split(" ")[0] ||
    user?.email?.split("@")[0] ||
    "Profissional";

  const handleSearch = async (query: string) => {
    if (!query.trim()) return;

    setIsSearching(true);
    // Simular busca com IA
    await new Promise((resolve) => setTimeout(resolve, 1500));
    setIsSearching(false);
    // TODO: Implementar lógica de busca real
  };

  const handleSuggestionClick = (suggestion: QuickSuggestion) => {
    setSearchQuery(suggestion.text);
    handleSearch(suggestion.text);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-10">
      {/* Header */}
      <div className="text-center space-y-4">
        <div className="inline-flex items-center gap-2 text-xs font-bold text-primary bg-primary/10 px-4 py-2 rounded-full">
          <span className="material-symbols-outlined text-sm">auto_awesome</span>
          HEAL+ AI SEARCH HUB
        </div>
        <h1 className="text-4xl font-extrabold font-headline text-on-surface">
          Como posso ajudar hoje,{" "}
          <span className="text-primary">Dr. {userName}</span>?
        </h1>
      </div>

      {/* Search Input */}
      <div className="relative">
        <div className="flex items-center bg-surface-container-lowest rounded-2xl border border-outline-variant/10 shadow-ambient overflow-hidden focus-within:border-primary/30 focus-within:ring-2 focus-within:ring-primary/10 transition-all">
          <div className="pl-6">
            <span className="material-symbols-outlined text-primary text-2xl">
              auto_awesome
            </span>
          </div>
          <input
            type="text"
            className="flex-grow bg-transparent border-none focus:ring-0 focus:outline-none text-lg py-5 px-4 text-on-surface placeholder:text-on-surface-variant font-body"
            placeholder="Pergunte qualquer coisa sobre seus pacientes, relatórios ou a plataforma..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch(searchQuery)}
          />
          <button
            onClick={() => handleSearch(searchQuery)}
            disabled={isSearching || !searchQuery.trim()}
            className="m-2 w-12 h-12 rounded-2xl bg-primary-container text-on-primary-container flex items-center justify-center shadow-ambient hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSearching ? (
              <span className="w-5 h-5 rounded-full border-2 border-white/30 border-t-white animate-spin"></span>
            ) : (
              <span className="material-symbols-outlined">arrow_forward</span>
            )}
          </button>
        </div>
      </div>

      {/* Quick Suggestions */}
      <div className="flex flex-wrap justify-center gap-3">
        {quickSuggestions.map((suggestion) => (
          <button
            key={suggestion.id}
            onClick={() => handleSuggestionClick(suggestion)}
            className="flex items-center gap-2 px-4 py-2.5 bg-surface-container-lowest rounded-full border border-outline-variant/10 hover:border-primary/20 transition-all text-sm text-on-surface-variant hover:text-on-surface group"
          >
            <span className="material-symbols-outlined text-base text-outline group-hover:text-primary transition-colors">
              {suggestion.icon}
            </span>
            {suggestion.text}
          </button>
        ))}
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 pt-4">
        {/* Recent Interactions */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold font-headline text-on-surface">
              Interações Recentes
            </h2>
            <button className="text-sm text-primary font-semibold hover:underline">
              Ver todas
            </button>
          </div>

          <div className="space-y-3">
            {recentInteractions.map((interaction) => (
              <div
                key={interaction.id}
                className="flex items-start gap-4 p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/5 hover:bg-surface-container-low transition-colors cursor-pointer group"
              >
                <div
                  className={`w-10 h-10 rounded-xl ${interaction.iconBg} flex items-center justify-center ${interaction.iconColor} flex-shrink-0`}
                >
                  <span className="material-symbols-outlined">
                    {interaction.icon}
                  </span>
                </div>
                <div className="flex-grow min-w-0">
                  <p className="font-semibold text-on-surface group-hover:text-primary transition-colors">
                    {interaction.title}
                  </p>
                  <p className="text-sm text-on-surface-variant truncate">
                    {interaction.description}
                  </p>
                </div>
                <span className="text-xs text-on-surface-variant flex-shrink-0">
                  {interaction.time}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Learn Heal+ */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold font-headline text-on-surface">
              Aprenda o Heal+
            </h2>
            <button className="text-sm text-primary font-semibold hover:underline">
              Ver tutoriais
            </button>
          </div>

          <div className="space-y-3">
            {tutorials.map((tutorial) => (
              <div
                key={tutorial.id}
                className="flex items-start gap-4 p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/5 hover:bg-surface-container-low transition-colors cursor-pointer group"
              >
                <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary flex-shrink-0">
                  <span className="material-symbols-outlined">
                    {tutorial.icon}
                  </span>
                </div>
                <div className="flex-grow min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-on-surface group-hover:text-primary transition-colors">
                      {tutorial.title}
                    </p>
                    {tutorial.badge && (
                      <span className="text-[10px] font-bold text-error bg-error/10 px-2 py-0.5 rounded-full animate-pulse">
                        {tutorial.badge}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-on-surface-variant">
                    {tutorial.description}
                  </p>
                </div>
                {tutorial.action && (
                  <button
                    className={`flex-shrink-0 px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
                      tutorial.action.variant === "primary"
                        ? "bg-primary-container text-on-primary-container hover:bg-primary-container/80"
                        : "bg-surface-container-high text-on-surface hover:bg-surface-container-highest"
                    }`}
                  >
                    {tutorial.action.label}
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Footer Hint */}
      <div className="text-center pt-6">
        <p className="text-sm text-on-surface-variant">
          <span className="material-symbols-outlined text-sm align-middle mr-1">
            lightbulb
          </span>
          Dica: Use linguagem natural para fazer perguntas, como "Mostre
          pacientes com úlcera diabética"
        </p>
      </div>
    </div>
  );
}
