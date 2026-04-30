import { CheckCircle2, AlertTriangle, XCircle, Info, X } from 'lucide-react';
import React, { createContext, useCallback, useContext, useState } from 'react';

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}

interface ToastContextValue {
  toast: (type: ToastType, message: string, duration?: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const icons: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle2 className="h-5 w-5 text-heal-success shrink-0" />,
  error: <XCircle className="h-5 w-5 text-heal-danger shrink-0" />,
  warning: <AlertTriangle className="h-5 w-5 text-heal-warning shrink-0" />,
  info: <Info className="h-5 w-5 text-heal-blue shrink-0" />,
};

const bgStyles: Record<ToastType, string> = {
  success: 'border-heal-success/20 bg-heal-successSoft dark:bg-green-950/60',
  error: 'border-heal-danger/20 bg-heal-dangerSoft dark:bg-red-950/60',
  warning: 'border-heal-warning/20 bg-heal-warningSoft dark:bg-amber-950/60',
  info: 'border-heal-blue/20 bg-heal-softBlue dark:bg-blue-950/60',
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = useCallback((type: ToastType, message: string, duration = 4000) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setToasts(prev => [...prev, { id, type, message, duration }]);

    if (duration > 0) {
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, duration);
    }
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toast: addToast }}>
      {children}
      <div className="toast-container">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`
              flex items-start gap-3 px-4 py-3
              rounded-xl border shadow-md
              backdrop-blur-sm
              animate-slide-down
              ${bgStyles[t.type]}
            `}
            role="alert"
          >
            {icons[t.type]}
            <p className="text-sm font-medium text-heal-ink dark:text-white flex-1 leading-relaxed">
              {t.message}
            </p>
            <button
              onClick={() => removeToast(t.id)}
              className="shrink-0 text-heal-muted hover:text-heal-ink dark:hover:text-white transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast deve ser usado dentro de ToastProvider');
  return context;
}
