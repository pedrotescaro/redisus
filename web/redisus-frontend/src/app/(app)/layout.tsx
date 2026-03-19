"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { onAuthStateChanged, type User } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { signOutUser } from "@/services/firebase/auth-service";

const navItems = [
  { label: "Pacientes", href: "/dashboard" },
  { label: "Nova Avaliacao", href: "/evaluations/new" },
  { label: "Comparacao", href: "/comparison" },
  { label: "Relatorios", href: "/reports" },
];

type AppLayoutProps = {
  children: React.ReactNode;
};

export default function AppLayout({ children }: AppLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (authUser) => {
      setUser(authUser);
      setLoading(false);

      if (!authUser) {
        router.replace("/login");
      }
    });

    return () => unsubscribe();
  }, [router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-600">
        Carregando ambiente clinico...
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-brand-100 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 md:px-6">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-brand-600">Redisus</p>
            <h2 className="text-lg font-semibold text-brand-900">Heal+ Workspace</h2>
          </div>
          <div className="text-right">
            <p className="text-sm text-slate-700">{user.email}</p>
            <button
              className="text-xs font-medium text-brand-700 hover:text-brand-900"
              onClick={async () => {
                await signOutUser();
                router.replace("/login");
              }}
            >
              Sair
            </button>
          </div>
        </div>
        <nav className="mx-auto flex max-w-7xl gap-1 px-4 pb-3 md:px-6">
          {navItems.map((item) => {
            const isActive = pathname === item.href;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-full px-4 py-2 text-sm transition ${
                  isActive
                    ? "bg-brand-600 text-white"
                    : "bg-brand-50 text-brand-800 hover:bg-brand-100"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-8 md:px-6">{children}</main>
    </div>
  );
}
