import {
  Bot,
  CalendarDays,
  ClipboardPlus,
  FileText,
  LayoutDashboard,
  ScanSearch,
  Settings,
  SplitSquareHorizontal,
  User,
  Users,
  X
} from 'lucide-react';
import type { ComponentType } from 'react';
import { NavLink } from 'react-router-dom';

import { BrandLogo } from '../brand/BrandLogo';

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
}

const primaryItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/patients', label: 'Pacientes', icon: Users },
  { to: '/evaluations/new', label: 'Avaliações', icon: ClipboardPlus },
  { to: '/agenda', label: 'Agenda', icon: CalendarDays },
  { to: '/reports', label: 'Relatórios', icon: FileText },
  { to: '/reports/compare', label: 'Comparar evolução', icon: SplitSquareHorizontal },
  { to: '/analyzer', label: 'HEAL Analyzer', icon: ScanSearch },
  { to: '/chat', label: 'Assistente', icon: Bot }
];

const secondaryItems = [
  { to: '/profile', label: 'Perfil', icon: User },
  { to: '/settings', label: 'Configurações', icon: Settings }
];

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col bg-white px-5 py-5 dark:bg-zinc-950">
      <BrandLogo className="mb-8" />
      <nav className="flex flex-1 flex-col gap-8">
        <div>
          <p className="mb-3 px-3 text-[0.68rem] font-black uppercase tracking-[0.18em] text-heal-muted">Clínica</p>
          <div className="space-y-1">
            {primaryItems.map(item => (
              <NavItem key={item.to} item={item} onNavigate={onNavigate} />
            ))}
          </div>
        </div>
        <div>
          <p className="mb-3 px-3 text-[0.68rem] font-black uppercase tracking-[0.18em] text-heal-muted">Conta</p>
          <div className="space-y-1">
            {secondaryItems.map(item => (
              <NavItem key={item.to} item={item} onNavigate={onNavigate} />
            ))}
          </div>
        </div>
      </nav>
      <div className="rounded-2xl bg-heal-softBlue p-4 dark:bg-blue-950/30">
        <p className="text-sm font-black text-heal-ink dark:text-white">Cuidado inteligente.</p>
        <p className="mt-1 text-xs leading-5 text-heal-muted dark:text-zinc-400">Evolução visível com registros reais no Firebase.</p>
      </div>
    </div>
  );
}

function NavItem({
  item,
  onNavigate
}: {
  item: { to: string; label: string; icon: ComponentType<{ className?: string }> };
  onNavigate?: () => void;
}) {
  return (
    <NavLink
      to={item.to}
      end={item.to === '/dashboard'}
      onClick={onNavigate}
      className={({ isActive }) =>
        `group flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-bold transition ${
          isActive
            ? 'bg-heal-softBlue text-heal-blue dark:bg-blue-950/40 dark:text-blue-200'
            : 'text-heal-muted hover:bg-slate-50 hover:text-heal-ink dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-white'
        }`
      }
    >
      <item.icon className="h-4 w-4 shrink-0" />
      {item.label}
    </NavLink>
  );
}

export function Sidebar({ isOpen, setIsOpen }: SidebarProps) {
  return (
    <>
      <aside className="hidden border-r border-heal-line bg-white dark:border-zinc-800 lg:fixed lg:inset-y-0 lg:z-40 lg:flex lg:w-[280px] lg:flex-col">
        <SidebarContent />
      </aside>

      {isOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/45 backdrop-blur-sm"
            aria-label="Fechar menu"
            onClick={() => setIsOpen(false)}
          />
          <aside className="relative h-full w-[min(86vw,320px)] border-r border-heal-line shadow-soft dark:border-zinc-800">
            <button
              type="button"
              className="absolute right-3 top-3 z-10 rounded-xl bg-white/80 p-2 text-heal-muted shadow-sm dark:bg-zinc-900"
              onClick={() => setIsOpen(false)}
              aria-label="Fechar sidebar"
            >
              <X className="h-5 w-5" />
            </button>
            <SidebarContent onNavigate={() => setIsOpen(false)} />
          </aside>
        </div>
      ) : null}
    </>
  );
}
