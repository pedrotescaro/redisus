"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { onAuthStateChanged, type User } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { signOutUser } from "@/services/firebase/auth-service";
import { Sidebar, TopAppBar } from "@/components/layout";
import { getClinicalApiHealth } from "@/services/clinical/clinical-api-service";

type AppLayoutProps = {
  children: React.ReactNode;
};

export default function AppLayout({ children }: AppLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiHealthy, setApiHealthy] = useState<boolean>(false);

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

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      const health = await getClinicalApiHealth();
      if (!mounted) return;
      setApiHealthy(health.status === "ok");
    };
    void check();
    const timer = setInterval(() => {
      void check();
    }, 15000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const handleLogout = async () => {
    await signOutUser();
    router.replace("/login");
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface">
        <div className="text-center">
          <div className="w-12 h-12 rounded-full border-2 border-primary-container border-t-transparent animate-spin mx-auto mb-4"></div>
          <p className="text-sm text-on-surface-variant font-body">
            Carregando ambiente clínico...
          </p>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  const userName = user.displayName || user.email?.split("@")[0] || "Usuário";

  return (
    <div className="flex min-h-screen bg-surface">
      <Sidebar onLogout={handleLogout} />

      <main className="flex-grow ml-64 min-h-screen bg-surface">
        <TopAppBar
          userName={userName}
          userEmail={user.email || undefined}
          userPhotoUrl={user.photoURL || undefined}
        />

        <div className="pt-24 px-8 pb-12 max-w-7xl mx-auto">
          <div className="mb-4">
            <span
              className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${
                apiHealthy ? "bg-green-500/15 text-green-400" : "bg-error/15 text-error"
              }`}
            >
              <span className="material-symbols-outlined text-sm">monitor_heart</span>
              API clínica {apiHealthy ? "online" : "offline"}
            </span>
          </div>
          {children}
        </div>
      </main>
    </div>
  );
}
