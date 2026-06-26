import { useEffect, useRef, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { useAuth } from '../../app/providers/AuthProvider';
import { useTheme } from '../../app/providers/ThemeProvider';
import type { ThemePreference } from '../../lib/types';
import { Sidebar } from './sidebar';
import { Topbar } from './Topbar';

export function AppShell() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const { profile } = useAuth();
  const { setTheme } = useTheme();
  const lastSyncedTheme = useRef<ThemePreference | null>(null);

  useEffect(() => {
    const profileTheme = profile?.settings?.theme;
    if (!profileTheme || profileTheme === lastSyncedTheme.current) return;
    lastSyncedTheme.current = profileTheme;
    setTheme(profileTheme);
  }, [profile?.settings?.theme, setTheme]);

  return (
    <div className="min-h-screen bg-heal-canvas text-heal-ink dark:bg-zinc-950">
      <Sidebar isOpen={isSidebarOpen} setIsOpen={setIsSidebarOpen} />

      <div className="flex flex-1 flex-col lg:pl-[280px]">
        <div className="lg:hidden">
          <Topbar onMenuClick={() => setIsSidebarOpen(true)} />
        </div>

        <main className="mx-auto w-full max-w-[1480px] flex-1 p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
