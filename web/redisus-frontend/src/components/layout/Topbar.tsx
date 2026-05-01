import { Bell, Menu, Search } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../app/providers/AuthProvider';
import { UserAvatar } from '../profile/UserAvatar';

interface TopbarProps {
  onMenuClick: () => void;
}

export function Topbar({ onMenuClick }: TopbarProps) {
  const { user, profile } = useAuth();
  const displayName = profile?.displayName || user?.displayName || user?.email || '';
  const photoURL = profile?.photoURL || user?.photoURL;

  return (
    <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center gap-x-4 border-b border-heal-line bg-white/85 px-4 shadow-sm backdrop-blur-xl sm:gap-x-6 sm:px-6 lg:px-8 dark:border-zinc-800 dark:bg-zinc-950/85">
      <button
        type="button"
        className="-m-2.5 p-2.5 text-heal-muted hover:text-heal-ink lg:hidden dark:text-zinc-400 dark:hover:text-white transition-colors"
        onClick={onMenuClick}
      >
        <span className="sr-only">Abrir sidebar</span>
        <Menu className="h-6 w-6" aria-hidden="true" />
      </button>

      <div className="flex flex-1 gap-x-4 self-stretch lg:gap-x-6">
        <form className="relative flex flex-1 items-center" action="#" method="GET">
          <label htmlFor="search-field" className="sr-only">Busca</label>
          <div className="relative w-full max-w-md">
            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-heal-muted dark:text-zinc-500" aria-hidden="true" />
            <input
              id="search-field"
              className="block h-10 w-full rounded-2xl border border-heal-line bg-heal-canvas pl-10 pr-4 text-sm text-heal-ink placeholder:text-slate-400 transition-colors focus:border-heal-blue focus:outline-none focus:ring-2 focus:ring-heal-blue/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white dark:placeholder-zinc-500"
              placeholder="Buscar pacientes..."
              type="search"
              name="search"
            />
          </div>
        </form>

        <div className="flex items-center gap-x-3 lg:gap-x-5">
          <Link to="/notifications" className="relative rounded-xl p-2 text-heal-muted transition-colors hover:bg-slate-100 hover:text-heal-ink dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-white">
            <span className="sr-only">Notificações</span>
            <Bell className="h-5 w-5" aria-hidden="true" />
          </Link>
          <div className="hidden lg:block lg:h-6 lg:w-px lg:bg-heal-line dark:lg:bg-zinc-800" aria-hidden="true" />
          <Link to="/profile" className="flex items-center gap-x-3 group">
            <span className="hidden lg:block text-sm font-medium text-heal-ink dark:text-white group-hover:text-heal-blue transition-colors truncate max-w-[160px]">
              {displayName}
            </span>
            <UserAvatar
              name={displayName}
              src={photoURL}
              imageClassName="h-9 w-9 rounded-xl bg-heal-canvas object-cover ring-2 ring-heal-line/50 transition-all group-hover:ring-heal-blue/30"
              fallbackClassName="flex h-9 w-9 items-center justify-center rounded-xl bg-heal-softBlue text-sm font-bold text-heal-blue ring-2 ring-heal-blue/10 group-hover:ring-heal-blue/30 transition-all dark:bg-blue-950/40"
            />
          </Link>
        </div>
      </div>
    </header>
  );
}
