import { useState } from 'react';
import {
  Bot,
  Building2,
  CalendarDays,
  ClipboardList,
  FileBarChart,
  GitCompareArrows,
  LayoutDashboard,
  LogOut,
  MoreHorizontal,
  ScanSearch,
  Settings,
  User as UserIcon,
  Users,
  X
} from 'lucide-react';
import type { ComponentType } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { signOut } from 'firebase/auth';
import { useAuth } from '../../app/providers/AuthProvider';
import { auth } from '../../lib/firebase';
import { UserAvatar } from '../profile/UserAvatar';

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
}

type RouteMatch = 'exact' | 'prefix';

interface NavItemConfig {
  to: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  match?: RouteMatch;
}

/* ──────────────────────────────────────────────
   Navigation items — flat list like DevDeck
   ────────────────────────────────────────────── */

const navItems: NavItemConfig[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, match: 'exact' },
  { to: '/patients', label: 'Pacientes', icon: Users, match: 'prefix' },
  { to: '/evaluations/new', label: 'Avaliações', icon: ClipboardList, match: 'exact' },
  { to: '/agenda', label: 'Agenda', icon: CalendarDays, match: 'exact' },
  { to: '/reports', label: 'Relatórios', icon: FileBarChart, match: 'exact' },
  { to: '/chat', label: 'Assistente', icon: Bot, match: 'exact' },
  { to: '/profile', label: 'Perfil', icon: UserIcon, match: 'prefix' }
];

/* Items inside the "Mais" dropdown */
const moreMenuItems: NavItemConfig[] = [
  { to: '/reports/compare', label: 'Comparar evolução', icon: GitCompareArrows, match: 'exact' },
  { to: '/analyzer', label: 'HEAL Analyzer', icon: ScanSearch, match: 'exact' },
  { to: '/settings', label: 'Configurações', icon: Settings, match: 'exact' }
];

/* ──────────────────────────────────────────────
   Helpers
   ────────────────────────────────────────────── */

function normalizePath(pathname: string) {
  if (pathname.length > 1 && pathname.endsWith('/')) {
    return pathname.slice(0, -1);
  }
  return pathname;
}

function isRouteActive(pathname: string, item: NavItemConfig) {
  const current = normalizePath(pathname);
  const target = normalizePath(item.to);
  if ((item.match ?? 'exact') === 'prefix') {
    return current === target || current.startsWith(`${target}/`);
  }
  return current === target;
}

/* ──────────────────────────────────────────────
   NavLink — Twitter-style sidebar link
   ────────────────────────────────────────────── */

function NavLink({ item, onClick }: { item: NavItemConfig; onClick?: () => void }) {
  const { pathname } = useLocation();
  const active = isRouteActive(pathname, item);
  const Icon = item.icon;

  return (
    <Link
      to={item.to}
      onClick={onClick}
      aria-current={active ? 'page' : undefined}
      className={`group flex items-center gap-3.5 py-2.5 px-3.5 rounded-xl text-sm font-semibold transition-all duration-200 border w-full cursor-pointer ${
        active
          ? 'bg-transparent text-heal-ink dark:text-white font-black border-transparent'
          : 'text-heal-muted border-transparent hover:bg-heal-surfaceHover dark:hover:bg-zinc-900 hover:text-heal-ink dark:hover:text-white dark:text-zinc-400'
      }`}
    >
      <div className="relative flex items-center justify-center w-5 h-5">
        <Icon
          className={`w-5 h-5 transition-transform group-hover:scale-105 duration-200 ${
            active
              ? 'text-heal-blue dark:text-blue-400'
              : 'text-heal-muted dark:text-zinc-400'
          }`}
        />
      </div>
      <span>{item.label}</span>
    </Link>
  );
}

/* ──────────────────────────────────────────────
   User Profile Widget (bottom of sidebar)
   ────────────────────────────────────────────── */

function UserProfileWidget({ onSignOut }: { onSignOut: () => void }) {
  const { user, profile } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const displayName = profile?.displayName || user?.displayName || user?.email || 'Usuário';
  const photoURL = profile?.photoURL || user?.photoURL;
  const email = profile?.email || user?.email || '';

  if (!user) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setDropdownOpen(!dropdownOpen)}
        className="group w-full flex items-center justify-between p-3 rounded-2xl border border-transparent hover:border-heal-line dark:hover:border-zinc-800 hover:bg-heal-surfaceHover/60 dark:hover:bg-zinc-900/60 transition-all duration-200 cursor-pointer"
      >
        <div className="flex items-center gap-3 min-w-0 flex-grow">
          <UserAvatar
            name={displayName}
            src={photoURL}
            imageClassName="w-10 h-10 rounded-full object-cover border border-heal-line dark:border-zinc-700 shrink-0"
            fallbackClassName="w-10 h-10 rounded-full bg-heal-softBlue dark:bg-blue-950/40 text-heal-blue flex items-center justify-center text-sm font-bold border border-heal-blue/10 shrink-0"
          />
          <div className="text-left min-w-0 flex-grow">
            <p className="text-sm font-bold text-heal-ink dark:text-white truncate leading-tight">
              {displayName}
            </p>
            <p className="text-[11px] text-heal-muted dark:text-zinc-500 font-medium truncate leading-none mt-1" title={email}>
              {email}
            </p>
          </div>
        </div>
        <MoreHorizontal className="w-5 h-5 text-heal-muted dark:text-zinc-500 shrink-0 transition-colors duration-200 group-hover:text-heal-ink dark:group-hover:text-white" />
      </button>

      {/* Dropdown menu */}
      {dropdownOpen && (
        <>
          <div
            className="fixed inset-0 z-40 cursor-default"
            onClick={() => setDropdownOpen(false)}
          />
          <div className="absolute bottom-full left-0 right-0 mb-2 rounded-xl border border-heal-line dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/95 backdrop-blur-xl shadow-lg z-50 py-1.5 overflow-hidden animate-slide-up">
            <Link
              to="/profile"
              className="flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-heal-ink dark:text-white hover:bg-heal-surfaceHover dark:hover:bg-zinc-800 transition-colors"
              onClick={() => setDropdownOpen(false)}
            >
              <UserIcon className="w-4 h-4 text-heal-muted dark:text-zinc-400" />
              Meu Perfil
            </Link>
            <Link
              to="/settings"
              className="flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-heal-ink dark:text-white hover:bg-heal-surfaceHover dark:hover:bg-zinc-800 transition-colors"
              onClick={() => setDropdownOpen(false)}
            >
              <Settings className="w-4 h-4 text-heal-muted dark:text-zinc-400" />
              Configurações
            </Link>
            <hr className="border-heal-line dark:border-zinc-800 my-1" />
            <button
              onClick={() => {
                setDropdownOpen(false);
                onSignOut();
              }}
              className="flex w-full items-center gap-2.5 px-4 py-2.5 text-xs font-bold text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 hover:text-red-600 dark:hover:text-red-400 transition-colors cursor-pointer"
            >
              <LogOut className="w-4 h-4 text-red-500" />
              Sair da Conta
            </button>
          </div>
        </>
      )}
    </div>
  );
}

/* ──────────────────────────────────────────────
   Desktop Sidebar Content
   ────────────────────────────────────────────── */

function MoreDropdown({ onNavigate }: { onNavigate?: () => void }) {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`group flex items-center gap-3.5 py-2.5 px-3.5 rounded-xl text-sm font-semibold transition-all duration-200 border w-full cursor-pointer text-heal-muted border-transparent hover:bg-heal-surfaceHover dark:hover:bg-zinc-900 hover:text-heal-ink dark:hover:text-white dark:text-zinc-400`}
      >
        <div className="relative flex items-center justify-center w-5 h-5">
          <MoreHorizontal className="w-5 h-5 text-heal-muted dark:text-zinc-400 transition-transform group-hover:scale-105 duration-200" />
        </div>
        <span>Mais</span>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40 cursor-default" onClick={() => setOpen(false)} />
          <div className="absolute bottom-full left-0 w-56 mb-2 rounded-xl border border-heal-line dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/95 backdrop-blur-xl shadow-lg z-50 py-1.5 overflow-hidden animate-slide-up">
            {moreMenuItems.map(item => {
              const Icon = item.icon;
              const active = isRouteActive(pathname, item);
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold transition-colors ${
                    active
                      ? 'text-heal-ink dark:text-white font-bold'
                      : 'text-heal-ink dark:text-white hover:bg-heal-surfaceHover dark:hover:bg-zinc-800'
                  }`}
                  onClick={() => { setOpen(false); onNavigate?.(); }}
                >
                  <Icon className="w-4 h-4 text-heal-muted dark:text-zinc-400" />
                  {item.label}
                </Link>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { profile } = useAuth();
  const handleSignOut = async () => {
    try {
      await signOut(auth);
    } catch (err) {
      console.error('Error signing out:', err);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col justify-between bg-white dark:bg-zinc-950 p-5 select-none">
      <div className="space-y-5">
        {/* Logo */}
        <Link to="/dashboard" className="flex items-center gap-3.5 px-3 py-1 group w-fit mb-2">
          <img
            src="/images/logo.png"
            alt="Heal+"
            className="h-11 w-11 object-contain group-hover:scale-105 transition-transform duration-300"
          />
          <span className="text-[32px] font-black tracking-tight text-heal-blue">
            Heal+
          </span>
        </Link>

        {/* Navigation — flat list like DevDeck */}
        <nav className="flex flex-col gap-0.5">
          {navItems.map(item => (
            <NavLink key={item.to} item={item} onClick={onNavigate} />
          ))}
          <MoreDropdown onNavigate={onNavigate} />
        </nav>
      </div>

      {/* Footer: user profile widget and institution */}
      <div className="shrink-0 space-y-2.5">
        <hr className="border-heal-line dark:border-zinc-800 mb-2" />
        {profile?.clinicName && (
          <div className="flex items-center gap-3 px-3.5 py-2 text-sm font-semibold text-heal-muted dark:text-zinc-400">
            <Building2 className="w-5 h-5 text-heal-muted dark:text-zinc-400 shrink-0" />
            <span className="truncate" title={profile.clinicName}>{profile.clinicName}</span>
          </div>
        )}
        <UserProfileWidget onSignOut={handleSignOut} />
      </div>
    </div>
  );
}

/* ──────────────────────────────────────────────
   Mobile Bottom Nav (Twitter-style)
   ────────────────────────────────────────────── */

const mobileNavItems = navItems.slice(0, 5); // Dashboard, Pacientes, Avaliações, Agenda, Relatórios

function MobileBottomNav() {
  const { pathname } = useLocation();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-white/90 dark:bg-zinc-950/90 backdrop-blur-md border-t border-heal-line dark:border-zinc-800 px-6 py-2.5 flex items-center justify-around lg:hidden">
      {mobileNavItems.map(item => {
        const Icon = item.icon;
        const active = isRouteActive(pathname, item);

        return (
          <Link
            key={item.to}
            to={item.to}
            className={`flex flex-col items-center justify-center p-1.5 transition-colors duration-150 ${
              active
                ? 'text-heal-blue font-black'
                : 'text-heal-muted dark:text-zinc-400 hover:text-heal-ink dark:hover:text-white'
            }`}
          >
            <div className="relative flex items-center justify-center">
              <Icon className={`w-[22px] h-[22px] ${active ? 'text-heal-blue' : ''}`} />
            </div>
          </Link>
        );
      })}
    </nav>
  );
}

/* ──────────────────────────────────────────────
   Sidebar Export (Desktop + Mobile)
   ────────────────────────────────────────────── */

export function Sidebar({ isOpen, setIsOpen }: SidebarProps) {
  return (
    <>
      {/* Desktop sidebar — fixed, Twitter-style */}
      <aside className="hidden h-screen w-[280px] border-r border-heal-line dark:border-zinc-800 bg-white dark:bg-zinc-950 lg:fixed lg:inset-y-0 lg:z-40 lg:flex lg:flex-col">
        <SidebarContent />
      </aside>

      {/* Mobile sidebar overlay */}
      {isOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/45 backdrop-blur-sm"
            aria-label="Fechar menu"
            onClick={() => setIsOpen(false)}
          />
          <aside className="relative h-full w-[min(86vw,320px)] min-w-[280px] border-r border-heal-line dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-lg">
            <button
              type="button"
              className="absolute right-3 top-3 z-10 rounded-xl bg-white/80 dark:bg-zinc-900 p-2 text-heal-muted shadow-sm"
              onClick={() => setIsOpen(false)}
              aria-label="Fechar sidebar"
            >
              <X className="h-5 w-5" />
            </button>
            <SidebarContent onNavigate={() => setIsOpen(false)} />
          </aside>
        </div>
      ) : null}

      {/* Mobile bottom navigation bar */}
      <MobileBottomNav />
    </>
  );
}
