"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type CSSProperties } from "react";
import { onAuthStateChanged, type User } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { signOutUser } from "@/services/firebase/auth-service";
import { Sidebar, TopAppBar } from "@/components/layout";
import { getClinicalApiHealth } from "@/services/clinical/clinical-api-service";

type AppLayoutProps = {
  children: React.ReactNode;
};

export default function AppLayout({ children }: AppLayoutProps) {
  const SIDEBAR_STORAGE_KEY = "healplus-sidebar-collapsed";
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiHealthy, setApiHealthy] = useState<boolean>(false);
  const [isDesktop, setIsDesktop] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const isStandaloneAnalyzer = pathname === "/analyzer";

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (authUser) => {
      setUser(authUser);
      setLoading(false);

      if (!authUser && !isStandaloneAnalyzer) {
        router.replace("/login");
      }
    });

    return () => unsubscribe();
  }, [isStandaloneAnalyzer, router]);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const media = window.matchMedia("(min-width: 1024px)");
    const syncDesktopState = () => setIsDesktop(media.matches);

    syncDesktopState();

    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", syncDesktopState);
      return () => media.removeEventListener("change", syncDesktopState);
    }

    media.addListener(syncDesktopState);
    return () => media.removeListener(syncDesktopState);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const storedPreference = window.localStorage.getItem(SIDEBAR_STORAGE_KEY);
    setIsSidebarCollapsed(storedPreference === "true");
  }, [SIDEBAR_STORAGE_KEY]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(
      SIDEBAR_STORAGE_KEY,
      String(isSidebarCollapsed),
    );
  }, [SIDEBAR_STORAGE_KEY, isSidebarCollapsed]);

  useEffect(() => {
    setIsMobileSidebarOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (isDesktop) {
      setIsMobileSidebarOpen(false);
    }
  }, [isDesktop]);

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

  const desktopSidebarWidth = isSidebarCollapsed ? "5.75rem" : "17.5rem";
  const layoutStyle = {
    "--sidebar-width": isDesktop ? desktopSidebarWidth : "0rem",
  } as CSSProperties;
  const contentContainerClass = isStandaloneAnalyzer
    ? "mx-auto w-full max-w-[1700px] px-4 pb-12 pt-28 sm:px-6 lg:px-8 xl:px-10"
    : "mx-auto max-w-7xl px-4 pb-12 pt-28 sm:px-6 lg:px-8";

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
    if (isStandaloneAnalyzer) {
      return (
        <div className="min-h-screen bg-surface">
          <div className="mx-auto max-w-[1800px] px-6 py-6 sm:px-8">
            <div className="mb-5">
              <span
                className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${
                  apiHealthy ? "bg-green-500/15 text-green-400" : "bg-error/15 text-error"
                }`}
              >
                <span className="material-symbols-outlined text-sm">monitor_heart</span>
                API clinica {apiHealthy ? "online" : "offline"}
              </span>
            </div>
            {children}
          </div>
        </div>
      );
    }

    return null;
  }

  const userName = user.displayName || user.email?.split("@")[0] || "Usuário";

  return (
    <div className="flex min-h-screen bg-surface" style={layoutStyle}>
      <Sidebar
        isCollapsed={isSidebarCollapsed}
        isDesktop={isDesktop}
        mobileOpen={isMobileSidebarOpen}
        onCollapseToggle={() => setIsSidebarCollapsed((current) => !current)}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
        onLogout={handleLogout}
      />

      <main className="min-h-screen flex-1 bg-surface transition-[margin] duration-300 lg:ml-[var(--sidebar-width)]">
        <TopAppBar
          userName={userName}
          userEmail={user.email || undefined}
          userPhotoUrl={user.photoURL || undefined}
          isSidebarCollapsed={isSidebarCollapsed}
          onDesktopSidebarToggle={() =>
            setIsSidebarCollapsed((current) => !current)
          }
          onMobileSidebarOpen={() => setIsMobileSidebarOpen(true)}
        />

        <div className={contentContainerClass}>
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
