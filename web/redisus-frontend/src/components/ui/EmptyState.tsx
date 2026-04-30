import { FolderOpen } from 'lucide-react';
import React from 'react';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className = '',
}: EmptyStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center text-center py-16 px-6 animate-fade-in ${className}`}>
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-heal-softBlue dark:bg-blue-950/30 mb-5">
        {icon || <FolderOpen className="h-7 w-7 text-heal-blue" />}
      </div>
      <h3 className="text-lg font-bold text-heal-ink dark:text-white mb-1.5">
        {title}
      </h3>
      {description && (
        <p className="text-sm text-heal-muted max-w-sm leading-relaxed mb-6">
          {description}
        </p>
      )}
      {action && <div>{action}</div>}
    </div>
  );
}
