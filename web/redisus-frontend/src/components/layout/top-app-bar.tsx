"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type TopAppBarProps = {
  userName: string;
  userRole?: string;
  userEmail?: string;
  userPhotoUrl?: string;
  isSidebarCollapsed: boolean;
  onDesktopSidebarToggle: () => void;
  onMobileSidebarOpen: () => void;
};

export function TopAppBar({
  userName,
  userRole = "Profissional de Saude",
  userEmail,
  userPhotoUrl,
  isSidebarCollapsed,
  onDesktopSidebarToggle,
  onMobileSidebarOpen,
}: TopAppBarProps) {
  const router = useRouter();
  const [isHovered, setIsHovered] = useState(false);

  const handleSearchClick = () => {
    router.push("/ai-search");
  };

  return (
    <header className="fixed left-0 right-0 top-0 z-40 flex h-20 items-center border-b border-outline-variant/10 bg-surface-container-lowest/72 px-4 shadow-[0_18px_40px_rgba(2,12,18,0.14)] backdrop-blur-xl transition-[left] duration-300 sm:px-6 lg:left-[var(--sidebar-width)] lg:px-8">
      <div className="flex min-w-0 flex-1 items-center gap-3 lg:gap-4">
        <button
          type="button"
          onClick={onMobileSidebarOpen}
          className="inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-outline-variant/12 bg-surface-container text-on-surface-variant transition-all hover:border-primary/20 hover:bg-primary/10 hover:text-primary lg:hidden"
          aria-label="Abrir menu lateral"
        >
          <span className="material-symbols-outlined">menu</span>
        </button>

        <button
          type="button"
          onClick={onDesktopSidebarToggle}
          className="hidden h-12 w-12 items-center justify-center rounded-2xl border border-outline-variant/12 bg-surface-container text-on-surface-variant transition-all hover:border-primary/20 hover:bg-primary/10 hover:text-primary lg:inline-flex"
          aria-label={
            isSidebarCollapsed ? "Expandir sidebar" : "Recolher sidebar"
          }
        >
          <span
            className={`material-symbols-outlined transition-transform duration-300 ${
              isSidebarCollapsed ? "rotate-180" : ""
            }`}
          >
            left_panel_open
          </span>
        </button>

        <div className="hidden min-w-0 lg:block">
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-on-surface-variant">
            Workspace Heal+
          </p>
          <p className="mt-1 truncate text-sm text-on-surface">
            Navegacao expansivel com atalhos clinicos
          </p>
        </div>
      </div>

      <div className="mx-3 hidden flex-1 justify-center lg:flex">
        <button
          onClick={handleSearchClick}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          className="group flex w-full max-w-[32rem] items-center rounded-full border border-transparent bg-surface-container px-4 py-3 text-left transition-all hover:border-primary/10 hover:bg-surface-container-high hover:ring-2 hover:ring-primary/20"
        >
          <span
            className={`material-symbols-outlined mr-3 text-lg transition-all duration-300 ${
              isHovered ? "text-primary" : "text-outline"
            }`}
          >
            {isHovered ? "auto_awesome" : "search"}
          </span>
          <span className="text-sm text-on-surface-variant transition-colors group-hover:text-on-surface">
            {isHovered
              ? "Buscar com IA em pacientes, avaliacoes e relatorios..."
              : "Buscar pacientes ou relatorios..."}
          </span>
        </button>
      </div>

      <div className="flex min-w-0 flex-1 items-center justify-end gap-2 sm:gap-3 lg:gap-5">
        <button
          onClick={handleSearchClick}
          className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-outline-variant/12 bg-surface-container text-on-surface-variant transition-all hover:border-primary/20 hover:bg-primary/10 hover:text-primary lg:hidden"
          aria-label="Abrir busca"
        >
          <span className="material-symbols-outlined">search</span>
        </button>

        <div className="hidden items-center gap-2 sm:flex">
          <button className="relative rounded-full p-2.5 text-on-surface-variant transition-all hover:bg-surface-container hover:text-on-surface">
            <span className="material-symbols-outlined">notifications</span>
            <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-error" />
          </button>
          <button className="rounded-full p-2.5 text-on-surface-variant transition-all hover:bg-surface-container hover:text-on-surface">
            <span className="material-symbols-outlined">help_outline</span>
          </button>
        </div>

        <div className="hidden h-8 w-px bg-outline-variant/15 sm:block" />

        <div className="group flex min-w-0 items-center gap-3 rounded-3xl border border-outline-variant/10 bg-surface-container px-3 py-2.5 transition-all hover:border-primary/16 hover:bg-surface-container-high">
          <div className="min-w-0 text-right">
            <p className="truncate text-sm font-bold leading-none text-on-surface">
              {userName}
            </p>
            <p className="mt-1 truncate text-[10px] font-medium uppercase tracking-[0.22em] text-primary">
              {userRole}
            </p>
            {userEmail && (
              <p className="mt-1 hidden truncate text-[11px] text-on-surface-variant xl:block">
                {userEmail}
              </p>
            )}
          </div>

          {userPhotoUrl ? (
            <img
              src={userPhotoUrl}
              alt={`${userName} Profile Picture`}
              className="h-11 w-11 rounded-full border-2 border-outline-variant/20 object-cover"
            />
          ) : (
            <div className="flex h-11 w-11 items-center justify-center rounded-full border-2 border-outline-variant/20 bg-surface-container-low">
              <span className="material-symbols-outlined text-on-surface-variant">
                person
              </span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
