"use client";

import { useTheme } from "@/contexts/theme-context";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-extrabold font-headline text-on-surface">
          Configurações
        </h1>
        <p className="text-on-surface-variant mt-1">
          Personalize sua experiência no Heal+
        </p>
      </div>

      {/* Settings Sections */}
      <div className="space-y-6">
        {/* Appearance */}
        <div className="bg-surface-container-lowest rounded-xl p-6 shadow-ambient">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
              <span className="material-symbols-outlined">palette</span>
            </div>
            <div>
              <h3 className="font-bold font-headline text-on-surface">
                Aparência
              </h3>
              <p className="text-sm text-on-surface-variant">
                Escolha o tema visual da interface
              </p>
            </div>
          </div>

          {/* Theme Options */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Light Mode */}
            <button
              onClick={() => setTheme("light")}
              className={`relative p-4 rounded-xl border-2 transition-all ${
                theme === "light"
                  ? "border-primary bg-primary/5"
                  : "border-outline-variant/20 hover:border-primary/30"
              }`}
            >
              <div className="flex flex-col items-center gap-3">
                <div
                  className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                    theme === "light"
                      ? "bg-primary text-white"
                      : "bg-surface-container text-on-surface-variant"
                  }`}
                >
                  <span className="material-symbols-outlined text-2xl">
                    light_mode
                  </span>
                </div>
                <span
                  className={`font-semibold ${
                    theme === "light" ? "text-primary" : "text-on-surface"
                  }`}
                >
                  Claro
                </span>
              </div>
              {theme === "light" && (
                <div className="absolute top-2 right-2">
                  <span className="material-symbols-outlined text-primary text-sm">
                    check_circle
                  </span>
                </div>
              )}
            </button>

            {/* Dark Mode */}
            <button
              onClick={() => setTheme("dark")}
              className={`relative p-4 rounded-xl border-2 transition-all ${
                theme === "dark"
                  ? "border-primary bg-primary/5"
                  : "border-outline-variant/20 hover:border-primary/30"
              }`}
            >
              <div className="flex flex-col items-center gap-3">
                <div
                  className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                    theme === "dark"
                      ? "bg-primary text-white"
                      : "bg-surface-container text-on-surface-variant"
                  }`}
                >
                  <span className="material-symbols-outlined text-2xl">
                    dark_mode
                  </span>
                </div>
                <span
                  className={`font-semibold ${
                    theme === "dark" ? "text-primary" : "text-on-surface"
                  }`}
                >
                  Escuro
                </span>
              </div>
              {theme === "dark" && (
                <div className="absolute top-2 right-2">
                  <span className="material-symbols-outlined text-primary text-sm">
                    check_circle
                  </span>
                </div>
              )}
            </button>

            {/* System (future feature placeholder) */}
            <div className="relative p-4 rounded-xl border-2 border-outline-variant/10 opacity-50 cursor-not-allowed">
              <div className="flex flex-col items-center gap-3">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-surface-container text-on-surface-variant">
                  <span className="material-symbols-outlined text-2xl">
                    contrast
                  </span>
                </div>
                <span className="font-semibold text-on-surface-variant">
                  Sistema
                </span>
              </div>
              <span className="absolute top-2 right-2 text-[10px] font-bold text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-full">
                EM BREVE
              </span>
            </div>
          </div>
        </div>

        {/* Notifications */}
        <div className="bg-surface-container-lowest rounded-xl p-6 shadow-ambient">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-tertiary/10 flex items-center justify-center text-tertiary">
              <span className="material-symbols-outlined">notifications</span>
            </div>
            <div>
              <h3 className="font-bold font-headline text-on-surface">
                Notificações
              </h3>
              <p className="text-sm text-on-surface-variant">
                Alertas e lembretes
              </p>
            </div>
          </div>
          <p className="text-sm text-on-surface-variant p-4 bg-surface-container rounded-lg">
            Configurações de notificações serão adicionadas em breve.
          </p>
        </div>

        {/* Data & Privacy */}
        <div className="bg-surface-container-lowest rounded-xl p-6 shadow-ambient">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-secondary/10 flex items-center justify-center text-secondary">
              <span className="material-symbols-outlined">security</span>
            </div>
            <div>
              <h3 className="font-bold font-headline text-on-surface">
                Dados e Privacidade
              </h3>
              <p className="text-sm text-on-surface-variant">
                Segurança e exportação de dados
              </p>
            </div>
          </div>
          <p className="text-sm text-on-surface-variant p-4 bg-surface-container rounded-lg">
            Opções de privacidade e exportação de dados serão adicionadas em
            breve.
          </p>
        </div>
      </div>

      {/* App Info */}
      <div className="text-center pt-6">
        <p className="text-xs text-on-surface-variant">
          Heal+ v1.0.0 • Redisus Platform
        </p>
      </div>
    </div>
  );
}
