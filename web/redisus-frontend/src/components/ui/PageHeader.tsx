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
}

export function PageHeader({ eyebrow, title, description, action, showBack, onBack }: PageHeaderProps) {
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
