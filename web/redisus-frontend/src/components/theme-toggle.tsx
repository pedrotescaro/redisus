"use client";

import { useTheme } from "@/contexts/theme-context";

export function ThemeToggle() {
  const { resolvedTheme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className="group relative flex h-10 w-10 items-center justify-center rounded-full border border-outline-variant/20 bg-surface-container-low text-on-surface-variant transition-all hover:bg-surface-container hover:text-on-surface hover:border-outline-variant/40 dark:hover:border-outline-variant/30"
      aria-label="Alternar tema"
    >
      <span className="material-symbols-outlined text-[20px] transition-transform duration-300 group-hover:scale-110">
        {resolvedTheme === "dark" ? "light_mode" : "dark_mode"}
      </span>
    </button>
  );
}
