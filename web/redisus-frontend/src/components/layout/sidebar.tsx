"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

type NavItem = {
  label: string;
  href: string;
  icon: string;
};

const navItems: NavItem[] = [
  { label: "Início", href: "/dashboard", icon: "dashboard" },
  { label: "Pacientes", href: "/patients", icon: "group" },
  { label: "Avaliações", href: "/evaluations/new", icon: "assignment" },
  { label: "Agenda", href: "/schedule", icon: "calendar_today" },
  { label: "Perfil", href: "/profile", icon: "person" },
];

const bottomNavItems: NavItem[] = [
  { label: "Configurações", href: "/settings", icon: "settings" },
];

type SidebarProps = {
  onLogout: () => void;
};

export function Sidebar({ onLogout }: SidebarProps) {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === "/dashboard") {
      return pathname === "/dashboard" || pathname === "/";
    }
    return pathname.startsWith(href);
  };

  return (
    <aside className="h-screen w-64 fixed left-0 top-0 bg-surface-container-low flex flex-col py-6 z-50 font-nav">
      {/* Logo */}
      <Link href="/dashboard" className="px-6 mb-10 flex items-center gap-2 group">
        <Image
          src="/images/logo.png"
          alt="Heal+ Logo"
          width={64}
          height={64}
          className="group-hover:scale-110 transition-transform"
        />
        <div className="-ml-1">
          <h1 className="text-2xl font-extrabold text-primary tracking-tight leading-none">
            Heal+
          </h1>
          <p className="text-[10px] text-on-surface-variant uppercase tracking-widest font-bold mt-0.5 opacity-70">
            Clinical Portal
          </p>
        </div>
      </Link>

      {/* Main Navigation */}
      <nav className="flex-grow space-y-1">
        {navItems.map((item) => {
          const active = isActive(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 mx-4 px-4 py-3 transition-all font-medium ${
                active
                  ? "text-white bg-primary-container rounded-lg shadow-sm"
                  : "text-on-surface-variant hover:text-on-surface hover:bg-primary/5"
              }`}
            >
              <span
                className="material-symbols-outlined"
                style={active ? { fontVariationSettings: "'FILL' 1" } : {}}
              >
                {item.icon}
              </span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Bottom Navigation */}
      <div className="mt-auto px-2 space-y-1">
        {bottomNavItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="flex items-center gap-3 px-4 py-3 text-on-surface-variant hover:text-on-surface transition-colors font-medium hover:bg-primary/5 rounded-lg"
          >
            <span className="material-symbols-outlined">{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        ))}

        <button
          onClick={onLogout}
          className="w-full flex items-center gap-3 px-4 py-3 text-error hover:text-error transition-colors font-medium hover:bg-error/10 rounded-lg"
        >
          <span className="material-symbols-outlined">logout</span>
          <span>Sair</span>
        </button>
      </div>
    </aside>
  );
}
