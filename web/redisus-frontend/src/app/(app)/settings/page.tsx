"use client";

import { useEffect, useState } from "react";
import { onAuthStateChanged } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { useTheme } from "@/contexts/theme-context";
import {
  getUserSettings,
  saveUserSettings,
  type NotificationPreferences,
  type AccessibilityPreferences,
} from "@/services/firebase/user-settings-service";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [uid, setUid] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [notificationPrefs, setNotificationPrefs] = useState<NotificationPreferences>({
    appointmentReminders: true,
    evaluationAlerts: true,
    weeklySummary: false,
  });
  const [accessibilityPrefs, setAccessibilityPrefs] = useState<AccessibilityPreferences>({
    largeText: false,
    highContrast: false,
    reducedMotion: false,
  });
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  // Listen for auth state
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setUid(user?.uid ?? null);
    });
    return () => unsubscribe();
  }, []);

  // Load settings from Firestore
  useEffect(() => {
    if (!uid) return;
    let active = true;
    void (async () => {
      try {
        const settings = await getUserSettings(uid);
        if (!active) return;
        setNotificationPrefs(settings.notifications);
        setAccessibilityPrefs(settings.accessibility);
      } catch {
        // Keep defaults on error
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [uid]);

  // Apply accessibility classes to the root element
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("a11y-large-text", accessibilityPrefs.largeText);
    root.classList.toggle("a11y-high-contrast", accessibilityPrefs.highContrast);
    root.classList.toggle("a11y-reduced-motion", accessibilityPrefs.reducedMotion);
  }, [accessibilityPrefs]);

  // Persist accessibility to Firestore
  useEffect(() => {
    if (!uid || loading) return;
    void saveUserSettings(uid, { accessibility: accessibilityPrefs });
  }, [accessibilityPrefs, uid, loading]);

  // Persist notifications to Firestore
  useEffect(() => {
    if (!uid || loading) return;
    void saveUserSettings(uid, { notifications: notificationPrefs });
  }, [notificationPrefs, uid, loading]);

  const notifySaved = (message: string) => {
    setSavedMessage(message);
    window.setTimeout(() => setSavedMessage(null), 2200);
  };

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
        <div className="panel-surface rounded-2xl p-6">
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
            {/* Light Mode (temporarily blocked) */}
            <button
              disabled
              aria-disabled="true"
              className="relative overflow-hidden p-4 rounded-2xl ghost-border opacity-50 cursor-not-allowed"
            >
              <div className="absolute inset-0 bg-gradient-to-br from-white/45 to-primary/5 pointer-events-none" />
              <div className="flex flex-col items-center gap-3">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center bg-surface-container text-on-surface-variant"
                >
                  <span className="material-symbols-outlined text-2xl">
                    light_mode
                  </span>
                </div>
                <span className="font-semibold text-on-surface-variant">Claro</span>
              </div>
              <span className="absolute top-2 right-2 text-[10px] font-bold text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-full">
                BLOQUEADO
              </span>
            </button>

            {/* Dark Mode */}
            <button
              onClick={() => setTheme("dark")}
              className={`relative overflow-hidden p-4 rounded-2xl transition-all ${
                theme === "dark"
                  ? "ghost-border bg-primary/10"
                  : "ghost-border hover:bg-surface-container-high/50"
              }`}
            >
              <div className="absolute inset-0 bg-gradient-to-br from-primary/15 via-transparent to-surface-container-high/80 pointer-events-none" />
              <div className="flex flex-col items-center gap-3">
                <div
                  className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                    theme === "dark"
                      ? "bg-primary-container text-on-primary-container shadow-ambient"
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
            <div className="relative p-4 rounded-2xl ghost-border opacity-50 cursor-not-allowed">
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
        <div className="panel-surface rounded-2xl p-6">
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
          <div className="space-y-3">
            <label className="flex items-center justify-between rounded-xl bg-surface-container p-3">
              <span className="text-sm text-on-surface">Lembretes de agendamento</span>
              <input
                type="checkbox"
                checked={notificationPrefs.appointmentReminders}
                onChange={(event) => {
                  setNotificationPrefs((prev) => ({
                    ...prev,
                    appointmentReminders: event.target.checked,
                  }));
                  notifySaved("Notificacoes atualizadas.");
                }}
              />
            </label>
            <label className="flex items-center justify-between rounded-xl bg-surface-container p-3">
              <span className="text-sm text-on-surface">Alertas de nova avaliação</span>
              <input
                type="checkbox"
                checked={notificationPrefs.evaluationAlerts}
                onChange={(event) => {
                  setNotificationPrefs((prev) => ({
                    ...prev,
                    evaluationAlerts: event.target.checked,
                  }));
                  notifySaved("Notificacoes atualizadas.");
                }}
              />
            </label>
            <label className="flex items-center justify-between rounded-xl bg-surface-container p-3">
              <span className="text-sm text-on-surface">Resumo semanal por e-mail</span>
              <input
                type="checkbox"
                checked={notificationPrefs.weeklySummary}
                onChange={(event) => {
                  setNotificationPrefs((prev) => ({
                    ...prev,
                    weeklySummary: event.target.checked,
                  }));
                  notifySaved("Notificacoes atualizadas.");
                }}
              />
            </label>
          </div>
        </div>

        {/* Accessibility */}
        <div className="panel-surface rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-secondary/10 flex items-center justify-center text-secondary">
              <span className="material-symbols-outlined">accessibility_new</span>
            </div>
            <div>
              <h3 className="font-bold font-headline text-on-surface">
                Acessibilidade
              </h3>
              <p className="text-sm text-on-surface-variant">
                Preferências de leitura e navegação
              </p>
            </div>
          </div>
          <div className="space-y-3">
            <label className="flex items-center justify-between rounded-xl bg-surface-container p-3">
              <span className="text-sm text-on-surface">Texto ampliado</span>
              <input
                type="checkbox"
                checked={accessibilityPrefs.largeText}
                onChange={(event) => {
                  setAccessibilityPrefs((prev) => ({
                    ...prev,
                    largeText: event.target.checked,
                  }));
                  notifySaved("Preferencias de acessibilidade aplicadas.");
                }}
              />
            </label>
            <label className="flex items-center justify-between rounded-xl bg-surface-container p-3">
              <span className="text-sm text-on-surface">Alto contraste</span>
              <input
                type="checkbox"
                checked={accessibilityPrefs.highContrast}
                onChange={(event) => {
                  setAccessibilityPrefs((prev) => ({
                    ...prev,
                    highContrast: event.target.checked,
                  }));
                  notifySaved("Preferencias de acessibilidade aplicadas.");
                }}
              />
            </label>
            <label className="flex items-center justify-between rounded-xl bg-surface-container p-3">
              <span className="text-sm text-on-surface">Reduzir animacoes</span>
              <input
                type="checkbox"
                checked={accessibilityPrefs.reducedMotion}
                onChange={(event) => {
                  setAccessibilityPrefs((prev) => ({
                    ...prev,
                    reducedMotion: event.target.checked,
                  }));
                  notifySaved("Preferencias de acessibilidade aplicadas.");
                }}
              />
            </label>
          </div>
        </div>

        {/* Data & Privacy */}
        <div className="panel-surface rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-secondary/10 flex items-center justify-center text-secondary">
              <span className="material-symbols-outlined">security</span>
            </div>
            <div>
              <h3 className="font-bold font-headline text-on-surface">Dados e Privacidade</h3>
              <p className="text-sm text-on-surface-variant">
                Security e exportacao de dados
              </p>
            </div>
          </div>
          <p className="text-sm text-on-surface-variant p-4 bg-surface-container rounded-lg">
            Seus dados clinicos permanecem vinculados ao Firebase e as exportacoes ficam no modulo de relatorios.
          </p>
        </div>
      </div>

      {savedMessage && (
        <div className="rounded-xl bg-primary/10 text-primary px-4 py-3 text-sm font-medium">
          {savedMessage}
        </div>
      )}

      {/* App Info */}
      <div className="text-center pt-6">
        <p className="text-xs text-on-surface-variant">
          Heal+ v1.0.0 • Redisus Platform
        </p>
      </div>
    </div>
  );
}
