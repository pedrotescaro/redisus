import { ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import type { ReactNode } from 'react';

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  showBack?: boolean;
  onBack?: () => void;
  showSidebarToggle?: boolean;
  isSidebarCollapsed?: boolean;
  onToggleSidebar?: () => void;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
  showBack,
  onBack,
  showSidebarToggle,
  isSidebarCollapsed,
  onToggleSidebar
}: PageHeaderProps) {
  const navigate = useNavigate();

  const handleBack = () => {
    if (onBack) {
      onBack();
    } else {
      navigate(-1);
    }
  };

  return (
    <header className="sticky top-0 z-30 bg-white/95 dark:bg-[#0c0c0e]/95 backdrop-blur-md border-b border-heal-line/60 dark:border-zinc-800/60 px-4 py-3 flex items-center justify-between gap-4 select-none">
      <div className="flex items-center gap-3.5 min-w-0 flex-1">
        {showSidebarToggle && onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            className="p-2 hover:bg-slate-50 dark:hover:bg-zinc-900 rounded-full transition-all text-heal-muted dark:text-[#8b8b93] hover:text-heal-ink dark:hover:text-white cursor-pointer"
            title={isSidebarCollapsed ? "Mostrar barra lateral" : "Ocultar barra lateral"}
          >
            {isSidebarCollapsed ? (
              <svg
                viewBox="0 0 24 24"
                className="w-5 h-5 fill-none stroke-current"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="19" y1="12" x2="5" y2="12" />
                <polyline points="12 19 5 12 12 5" />
              </svg>
            ) : (
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="w-5 h-5"
              >
                <rect width="18" height="18" x="3" y="3" rx="4" />
                <path d="M9 3v18" />
              </svg>
            )}
          </button>
        )}
        {showBack && (
          <button
            onClick={handleBack}
            className="p-2 hover:bg-slate-50 dark:hover:bg-zinc-900 rounded-full transition-colors text-heal-ink dark:text-white cursor-pointer"
            title="Voltar"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
        )}
        <div className="min-w-0">
          <h1 className="text-heal-ink dark:text-white text-base font-extrabold tracking-tight truncate leading-tight">
            {title}
          </h1>
          {(eyebrow || description) && (
            <p className="text-heal-muted dark:text-zinc-500 text-[10px] uppercase font-bold tracking-wider mt-0.5 truncate">
              {eyebrow || description}
            </p>
          )}
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </header>
  );
}
