"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { onAuthStateChanged, type User } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { signOutUser } from "@/services/firebase/auth-service";
import { Sidebar, TopAppBar } from "@/components/layout";

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
          {children}
        </div>
      </main>
    </div>
  );
}
