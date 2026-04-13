"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

type SidebarLinkItem = {
  id: string;
  label: string;
  href: string;
  icon: string;
};

type SidebarGroupItem = {
  id: string;
  label: string;
  icon: string;
  items: SidebarLinkItem[];
};

type SidebarEntry =
  | ({ type: "link" } & SidebarLinkItem)
  | ({ type: "group" } & SidebarGroupItem);

type SidebarSection = {
  id: string;
  label: string;
  entries: SidebarEntry[];
};

const mainEntries: SidebarEntry[] = [
  {
    type: "link",
    id: "dashboard",
    label: "Inicio",
    href: "/dashboard",
    icon: "dashboard",
  },
  {
    type: "link",
    id: "analyzer",
    label: "HEAL Analyzer",
    href: "/analyzer",
    icon: "neurology",
  },
  {
    type: "group",
    id: "clinical-flow",
    label: "Fluxo clinico",
    icon: "assignment",
    items: [
      {
        id: "patients",
        label: "Pacientes",
        href: "/patients",
        icon: "group",
      },
      {
        id: "evaluations",
        label: "Avaliacoes",
        href: "/evaluations/new",
        icon: "assignment_turned_in",
      },
      {
        id: "comparison",
        label: "Comparar",
        href: "/comparison",
        icon: "compare_arrows",
      },
      {
        id: "reports",
        label: "Relatorios",
        href: "/reports",
        icon: "summarize",
      },
    ],
  },
  {
    type: "link",
    id: "schedule",
    label: "Agenda",
    href: "/schedule",
    icon: "calendar_today",
  },
];

const accountEntries: SidebarEntry[] = [
  {
    type: "link",
    id: "profile",
    label: "Perfil",
    href: "/profile",
    icon: "person",
  },
  {
    type: "link",
    id: "settings",
    label: "Configuracoes",
    href: "/settings",
    icon: "settings",
  },
];

const sections: SidebarSection[] = [
  { id: "main", label: "Principal", entries: mainEntries },
  { id: "account", label: "Conta", entries: accountEntries },
];

type SidebarProps = {
  isCollapsed: boolean;
  isDesktop: boolean;
  mobileOpen: boolean;
  onCollapseToggle: () => void;
  onCloseMobile: () => void;
  onLogout: () => void;
};

function isLinkActive(pathname: string, href: string) {
  if (href === "/dashboard") {
    return pathname === "/dashboard" || pathname === "/";
  }

  return pathname.startsWith(href);
}

function sectionHasActiveEntry(pathname: string, entries: SidebarEntry[]) {
  return entries.some((entry) =>
    entry.type === "link"
      ? isLinkActive(pathname, entry.href)
      : entry.items.some((item) => isLinkActive(pathname, item.href)),
  );
}

export function Sidebar({
  isCollapsed,
  isDesktop,
  mobileOpen,
  onCollapseToggle,
  onCloseMobile,
  onLogout,
}: SidebarProps) {
  const pathname = usePathname();
  const compactMode = isDesktop && isCollapsed;
  const panelWidth = compactMode ? "5.5rem" : isDesktop ? "16rem" : "17.5rem";

  const activeGroupIds = useMemo(
    () =>
      mainEntries
        .filter(
          (entry) =>
            entry.type === "group" &&
            entry.items.some((item) => isLinkActive(pathname, item.href)),
        )
        .map((entry) => entry.id),
    [pathname],
  );

  const [openGroups, setOpenGroups] = useState<string[]>(activeGroupIds);
  const [hoveredPopupId, setHoveredPopupId] = useState<string | null>(null);

  useEffect(() => {
    setOpenGroups((current) =>
      Array.from(new Set([...current, ...activeGroupIds])),
    );
  }, [activeGroupIds]);

  useEffect(() => {
    if (!compactMode) {
      setHoveredPopupId(null);
    }
  }, [compactMode]);

  const handleNavClick = () => {
    if (!isDesktop) {
      onCloseMobile();
    }
  };

  const toggleGroup = (groupId: string) => {
    setOpenGroups((current) =>
      current.includes(groupId)
        ? current.filter((item) => item !== groupId)
        : [...current, groupId],
    );
  };

  const showCompactPopup = (popupId: string) => {
    if (compactMode) {
      setHoveredPopupId(popupId);
    }
  };

  const hideCompactPopup = (popupId: string) => {
    if (compactMode) {
      setHoveredPopupId((current) => (current === popupId ? null : current));
    }
  };

  return (
    <>
      <div
        onClick={onCloseMobile}
        aria-hidden="true"
        className={`fixed inset-0 z-40 bg-[#06131c]/55 backdrop-blur-sm transition-opacity duration-300 lg:hidden ${
          mobileOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
      />

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex flex-col border-r border-outline-variant/10 bg-surface-container-lowest/96 shadow-[0_24px_80px_rgba(3,12,19,0.32)] backdrop-blur-xl transition-[width,transform] duration-300 ease-out ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        } lg:translate-x-0`}
        style={{ width: panelWidth }}
      >
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(83,177,253,0.12),transparent_32%),linear-gradient(180deg,rgba(255,255,255,0.02),transparent_28%)]" />

        <div className="relative flex h-full flex-col">
          <div
            className={`flex items-center px-4 pb-4 pt-5 ${
              compactMode ? "justify-center" : "justify-between gap-3"
            }`}
          >
            <Link
              href="/dashboard"
              onClick={handleNavClick}
              className={`group flex min-w-0 items-center ${
                compactMode ? "justify-center" : "gap-3"
              }`}
            >
              <div className="relative flex h-14 w-14 flex-shrink-0 items-center justify-center overflow-hidden rounded-3xl border border-primary/10 bg-surface-container shadow-[0_10px_26px_rgba(6,34,44,0.18)]">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_30%,rgba(83,177,253,0.18),transparent_45%),radial-gradient(circle_at_72%_72%,rgba(59,130,246,0.12),transparent_48%)]" />
                <Image
                  src="/images/logo.png"
                  alt="Heal+ Logo"
                  width={42}
                  height={42}
                  className="relative transition-transform duration-300 group-hover:scale-110"
                />
              </div>

              <div
                className={`overflow-hidden transition-[max-width,opacity,transform] duration-300 ${
                  compactMode
                    ? "max-w-0 -translate-x-2 opacity-0"
                    : "max-w-[140px] translate-x-0 opacity-100"
                }`}
              >
                <h1 className="text-[2rem] font-extrabold leading-none tracking-tight text-primary">
                  Heal+
                </h1>
                <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.32em] text-on-surface-variant">
                  Plataforma clinica
                </p>
              </div>
            </Link>

            {isDesktop ? (
              <button
                type="button"
                onClick={onCollapseToggle}
                className="hidden h-11 w-11 items-center justify-center rounded-full border border-outline-variant/12 bg-surface-container text-on-surface-variant transition-all hover:border-primary/20 hover:bg-primary/10 hover:text-primary lg:inline-flex"
                aria-label={
                  compactMode ? "Expandir sidebar" : "Recolher sidebar"
                }
              >
                <span
                  className={`material-symbols-outlined transition-transform duration-300 ${
                    compactMode ? "rotate-180" : ""
                  }`}
                >
                  keyboard_double_arrow_left
                </span>
              </button>
            ) : (
              <button
                type="button"
                onClick={onCloseMobile}
                className="ml-auto inline-flex h-11 w-11 items-center justify-center rounded-full border border-outline-variant/12 bg-surface-container text-on-surface-variant transition-all hover:border-primary/20 hover:bg-primary/10 hover:text-primary"
                aria-label="Fechar menu"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            )}
          </div>

          <nav className="flex-1 overflow-y-auto px-3 pb-4">
            {sections.map((section) => (
              <div key={section.id} className="mb-6">
                <div
                  className={`px-3 pb-2 text-[10px] font-bold uppercase tracking-[0.24em] text-on-surface-variant transition-opacity duration-300 ${
                    compactMode ? "opacity-0" : "opacity-100"
                  }`}
                >
                  {section.label}
                </div>

                <div
                  className={`space-y-1 ${
                    !compactMode &&
                    sectionHasActiveEntry(pathname, section.entries) &&
                    "rounded-[1.75rem] border border-outline-variant/10 bg-surface-container-low/70 p-2"
                  }`}
                >
                  {section.entries.map((entry) => {
                    if (entry.type === "link") {
                      const active = isLinkActive(pathname, entry.href);

                      return (
                        <div
                          key={entry.id}
                          className="relative"
                          onMouseEnter={() => showCompactPopup(entry.id)}
                          onMouseLeave={() => hideCompactPopup(entry.id)}
                        >
                          <Link
                            href={entry.href}
                            prefetch
                            aria-current={active ? "page" : undefined}
                            onClick={handleNavClick}
                            className={`group flex items-center rounded-2xl px-3 py-3 transition-all ${
                              compactMode ? "justify-center" : "gap-3"
                            } ${
                              active
                                ? "bg-primary-gradient text-on-primary-container shadow-ambient"
                                : "text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
                            }`}
                          >
                            <span
                              className="material-symbols-outlined"
                              style={
                                active ? { fontVariationSettings: "'FILL' 1" } : {}
                              }
                            >
                              {entry.icon}
                            </span>
                            <span
                              className={`overflow-hidden whitespace-nowrap text-sm font-medium transition-[max-width,opacity,transform] duration-300 ${
                                compactMode
                                  ? "max-w-0 -translate-x-2 opacity-0"
                                  : "max-w-[150px] translate-x-0 opacity-100"
                              }`}
                            >
                              {entry.label}
                            </span>
                          </Link>

                          {compactMode && hoveredPopupId === entry.id && (
                            <div className="absolute left-full top-1/2 z-30 ml-4 hidden -translate-y-1/2 rounded-xl bg-[#0B1118] px-3 py-2 text-sm font-medium text-white shadow-[0_18px_40px_rgba(2,10,18,0.34)] lg:block">
                              {entry.label}
                            </div>
                          )}
                        </div>
                      );
                    }

                    const groupActive = entry.items.some((item) =>
                      isLinkActive(pathname, item.href),
                    );
                    const groupOpen = openGroups.includes(entry.id);

                    return (
                      <div
                        key={entry.id}
                        className="relative"
                        onMouseEnter={() => showCompactPopup(entry.id)}
                        onMouseLeave={() => hideCompactPopup(entry.id)}
                      >
                        <button
                          type="button"
                          aria-expanded={
                            compactMode ? hoveredPopupId === entry.id : groupOpen
                          }
                          aria-haspopup={compactMode ? "menu" : undefined}
                          onClick={() =>
                            compactMode
                              ? setHoveredPopupId((current) =>
                                  current === entry.id ? null : entry.id,
                                )
                              : toggleGroup(entry.id)
                          }
                          className={`group flex w-full items-center rounded-2xl px-3 py-3 text-left transition-all ${
                            compactMode ? "justify-center" : "gap-3"
                          } ${
                            groupActive
                              ? "bg-primary/10 text-primary"
                              : "text-on-surface-variant hover:bg-surface-container hover:text-on-surface"
                          }`}
                        >
                          <span className="material-symbols-outlined">
                            {entry.icon}
                          </span>
                          <div
                            className={`flex min-w-0 flex-1 items-center justify-between gap-3 overflow-hidden transition-[max-width,opacity,transform] duration-300 ${
                              compactMode
                                ? "max-w-0 -translate-x-2 opacity-0"
                                : "max-w-[170px] translate-x-0 opacity-100"
                            }`}
                          >
                            <span className="truncate text-sm font-medium">
                              {entry.label}
                            </span>
                            <span
                              className={`material-symbols-outlined text-base transition-transform duration-300 ${
                                groupOpen ? "rotate-180" : ""
                              }`}
                            >
                              expand_more
                            </span>
                          </div>
                        </button>

                        {!compactMode && groupOpen && (
                          <div className="ml-5 mt-1 border-l border-outline-variant/10 pl-4">
                            {entry.items.map((item) => {
                              const active = isLinkActive(pathname, item.href);

                              return (
                                <Link
                                  key={item.id}
                                  href={item.href}
                                  prefetch
                                  aria-current={active ? "page" : undefined}
                                  onClick={handleNavClick}
                                  className={`mt-1 flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm transition-all ${
                                    active
                                      ? "bg-primary-gradient text-on-primary-container shadow-ambient"
                                      : "text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface"
                                  }`}
                                >
                                  <span
                                    className="material-symbols-outlined text-[19px]"
                                    style={
                                      active
                                        ? { fontVariationSettings: "'FILL' 1" }
                                        : {}
                                    }
                                  >
                                    {item.icon}
                                  </span>
                                  <span className="truncate font-medium">
                                    {item.label}
                                  </span>
                                </Link>
                              );
                            })}
                          </div>
                        )}

                        {compactMode && hoveredPopupId === entry.id && (
                          <div
                            role="menu"
                            className="absolute left-full top-1/2 z-30 ml-4 hidden w-56 -translate-y-1/2 rounded-2xl border border-outline-variant/10 bg-[#FAFAF8] p-2 text-[#16191D] shadow-[0_22px_48px_rgba(2,10,18,0.24)] lg:block"
                          >
                            <p className="px-3 pb-2 pt-1 text-[10px] font-bold uppercase tracking-[0.24em] text-[#7B8490]">
                              {entry.label}
                            </p>
                            <div className="space-y-1">
                              {entry.items.map((item) => {
                                const active = isLinkActive(pathname, item.href);

                                return (
                                  <Link
                                    key={item.id}
                                    href={item.href}
                                    prefetch
                                    role="menuitem"
                                    aria-current={active ? "page" : undefined}
                                    onClick={handleNavClick}
                                    className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors ${
                                      active
                                        ? "bg-[#F1F2F4] font-semibold text-[#16191D]"
                                        : "text-[#555D68] hover:bg-[#F5F5F4] hover:text-[#16191D]"
                                    }`}
                                  >
                                    <span className="material-symbols-outlined text-[18px]">
                                      {item.icon}
                                    </span>
                                    <span>{item.label}</span>
                                  </Link>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>

          <div className="mt-auto px-3 pb-4">
            <div className="border-t border-outline-variant/10 pt-3">
              <div
                className="relative"
                onMouseEnter={() => showCompactPopup("logout")}
                onMouseLeave={() => hideCompactPopup("logout")}
              >
                <button
                  type="button"
                  onClick={onLogout}
                  className={`flex w-full items-center rounded-2xl px-3 py-3 text-error transition-all hover:bg-error/10 ${
                    compactMode ? "justify-center" : "gap-3"
                  }`}
                >
                  <span className="material-symbols-outlined">logout</span>
                  <span
                    className={`overflow-hidden whitespace-nowrap text-sm font-semibold transition-[max-width,opacity,transform] duration-300 ${
                      compactMode
                        ? "max-w-0 -translate-x-2 opacity-0"
                        : "max-w-[120px] translate-x-0 opacity-100"
                    }`}
                  >
                    Sair
                  </span>
                </button>

                {compactMode && hoveredPopupId === "logout" && (
                  <div className="absolute left-full top-1/2 z-30 ml-4 hidden -translate-y-1/2 rounded-xl bg-[#0B1118] px-3 py-2 text-sm font-medium text-white shadow-[0_18px_40px_rgba(2,10,18,0.34)] lg:block">
                    Encerrar sessao
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
