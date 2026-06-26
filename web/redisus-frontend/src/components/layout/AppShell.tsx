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
    <div className="min-h-screen bg-white dark:bg-[#0c0c0e] text-heal-ink dark:text-zinc-200 antialiased flex flex-col md:flex-row">
      <Sidebar isOpen={isSidebarOpen} setIsOpen={setIsSidebarOpen} />

      <div className="flex-1 flex flex-col lg:pl-[280px] min-w-0">
        <div className="lg:hidden">
          <Topbar onMenuClick={() => setIsSidebarOpen(true)} />
        </div>

        <main className="flex-grow flex flex-col min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
