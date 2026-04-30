import { X } from 'lucide-react';
import type { ReactNode } from 'react';

interface ModalProps {
  open: boolean;
  title?: string;
  onClose: () => void;
  children: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  maxWidth?: string;
}

const sizeClasses = {
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-5xl'
};

export function Modal({ open, title, onClose, children, size = 'md', maxWidth }: ModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <button type="button" className="fixed inset-0 bg-slate-950/45 backdrop-blur-sm" aria-label="Fechar modal" onClick={onClose} />
      <div className="flex min-h-full items-center justify-center p-4">
        <section
          className={`relative w-full ${maxWidth || sizeClasses[size]} overflow-hidden rounded-[1.25rem] border border-heal-line bg-white shadow-soft dark:border-zinc-800 dark:bg-zinc-900`}
          role="dialog"
          aria-modal="true"
          aria-label={title}
        >
          {title ? (
            <div className="flex items-center justify-between border-b border-heal-line px-6 py-4 dark:border-zinc-800">
              <h2 className="text-lg font-black text-heal-ink dark:text-white">{title}</h2>
              <button
                type="button"
                onClick={onClose}
                className="flex h-8 w-8 items-center justify-center rounded-xl text-heal-muted transition hover:bg-slate-100 hover:text-heal-ink dark:hover:bg-zinc-800 dark:hover:text-white"
                aria-label="Fechar"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : null}
          <div className="p-6">{children}</div>
        </section>
      </div>
    </div>
  );
}
