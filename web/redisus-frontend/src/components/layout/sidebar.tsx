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
import type { ComponentType, ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
}

type RouteMatch = 'exact' | 'prefix';

interface SidebarItemConfig {
  to: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  match?: RouteMatch;
}

interface SidebarSectionConfig {
  title: string;
  items: SidebarItemConfig[];
}

const primaryItems: SidebarItemConfig[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, match: 'exact' },
  { to: '/patients', label: 'Pacientes', icon: Users, match: 'prefix' },
  { to: '/evaluations/new', label: 'Avaliações', icon: ClipboardPlus, match: 'exact' },
  { to: '/agenda', label: 'Agenda', icon: CalendarDays, match: 'exact' },
  { to: '/reports', label: 'Relatórios', icon: FileText, match: 'exact' },
  { to: '/reports/compare', label: 'Comparar evolução', icon: SplitSquareHorizontal, match: 'exact' },
  { to: '/analyzer', label: 'HEAL Analyzer', icon: ScanSearch, match: 'exact' },
  { to: '/chat', label: 'Assistente', icon: Bot, match: 'exact' }
];

const accountItems: SidebarItemConfig[] = [
  { to: '/profile', label: 'Perfil', icon: User, match: 'prefix' },
  { to: '/settings', label: 'Configurações', icon: Settings, match: 'exact' }
];

const sections: SidebarSectionConfig[] = [
  { title: 'Clínica', items: primaryItems },
  { title: 'Conta', items: accountItems }
];

function normalizePath(pathname: string) {
  if (pathname.length > 1 && pathname.endsWith('/')) {
    return pathname.slice(0, -1);
  }

  return pathname;
}

function isRouteActive(pathname: string, item: SidebarItemConfig) {
  const current = normalizePath(pathname);
  const target = normalizePath(item.to);

  if ((item.match ?? 'exact') === 'prefix') {
    return current === target || current.startsWith(`${target}/`);
  }

  return current === target;
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full min-h-0 flex-col bg-white p-5 dark:bg-zinc-950">
      <div className="sidebar-scroll flex min-h-0 flex-1 flex-col gap-8 overflow-y-auto pr-1">
        <SidebarBrandLogo />
        <nav className="flex flex-col gap-7">
          {sections.map(section => (
            <SidebarSection key={section.title} title={section.title}>
              {section.items.map(item => (
                <SidebarItem key={item.to} item={item} onNavigate={onNavigate} />
              ))}
            </SidebarSection>
          ))}
        </nav>
      </div>
      <SidebarFooterCard />
    </div>
  );
}

function SidebarBrandLogo() {
  return (
    <div className="flex items-center gap-3 px-2">
      <img src="/images/logo.png" alt="Heal+" className="h-11 w-11 shrink-0 object-contain" />
      <div>
        <p className="text-[2.05rem] font-black leading-none tracking-[-0.03em] text-[#3b82f6]">Heal+</p>
        <p className="text-xs font-semibold text-heal-muted">Plataforma clínica</p>
      </div>
    </div>
  );
}

function SidebarSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <p className="mb-2 px-2 text-[0.68rem] font-black uppercase tracking-[0.18em] text-heal-muted">{title}</p>
      <div className="space-y-1">{children}</div>
    </section>
  );
}

function SidebarItem({
  item,
  onNavigate
}: {
  item: SidebarItemConfig;
  onNavigate?: () => void;
}) {
  const { pathname } = useLocation();
  const isActive = isRouteActive(pathname, item);

  return (
    <Link
      to={item.to}
      onClick={onNavigate}
      aria-current={isActive ? 'page' : undefined}
      className={`group flex h-11 items-center gap-3 rounded-2xl px-3 text-sm transition-colors ${
        isActive
          ? 'bg-blue-100 font-semibold text-blue-600 dark:bg-blue-950/45 dark:text-blue-200'
          : 'font-semibold text-slate-600 hover:bg-slate-100 hover:text-heal-ink dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-white'
      }`}
    >
      <item.icon className={`h-4 w-4 shrink-0 transition-colors ${isActive ? 'text-blue-600 dark:text-blue-200' : 'text-slate-500 dark:text-zinc-400'}`} />
      <span className="truncate leading-5">{item.label}</span>
    </Link>
  );
}

function SidebarFooterCard() {
  return (
    <div className="mt-5 shrink-0 rounded-2xl bg-blue-100 p-4 dark:bg-blue-950/30">
      <p className="text-sm font-black text-heal-ink dark:text-white">Cuidado inteligente.</p>
      <p className="mt-1 text-xs leading-5 text-heal-muted dark:text-zinc-400">Evolução visível com registros reais no Firebase.</p>
    </div>
  );
}

export function Sidebar({ isOpen, setIsOpen }: SidebarProps) {
  return (
    <>
      <aside className="hidden h-screen w-[280px] border-r border-heal-line bg-white dark:border-zinc-800 lg:fixed lg:inset-y-0 lg:z-40 lg:flex lg:flex-col">
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
          <aside className="relative h-full w-[min(86vw,320px)] min-w-[280px] border-r border-heal-line bg-white shadow-soft dark:border-zinc-800 dark:bg-zinc-950">
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
