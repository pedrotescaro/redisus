import { Loader2 } from 'lucide-react';

interface LoadingStateProps {
  label?: string;
  variant?: 'spinner' | 'skeleton';
  rows?: number;
}

export function LoadingState({ label = 'Carregando...', variant = 'spinner', rows = 4 }: LoadingStateProps) {
  if (variant === 'skeleton') {
    return (
      <div className="space-y-4 animate-fade-in p-1">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex gap-4 items-center">
            <div className="skeleton h-12 w-12 rounded-xl shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="skeleton h-4 w-3/4 rounded" />
              <div className="skeleton h-3 w-1/2 rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center py-20 animate-fade-in gap-4">
      <div className="relative">
        <div className="absolute inset-0 rounded-full bg-heal-blue/10 animate-ping" />
        <div className="relative flex h-12 w-12 items-center justify-center rounded-full bg-heal-softBlue dark:bg-blue-950/30">
          <Loader2 className="h-6 w-6 text-heal-blue animate-spin" />
        </div>
      </div>
      <p className="text-sm font-medium text-heal-muted">{label}</p>
    </div>
  );
}
