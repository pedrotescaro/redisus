import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
  padding?: 'sm' | 'md' | 'lg' | 'none';
}

const paddings = {
  none: '',
  sm: 'p-4',
  md: 'p-5 sm:p-6',
  lg: 'p-6 sm:p-8',
};

export function Card({ children, className = '', hover = false, padding = 'md' }: CardProps) {
  return (
    <div
      className={`
        bg-white dark:bg-[#0c0c0e]
        border border-heal-line/75 dark:border-zinc-800/80
        rounded-2xl shadow-sm dark:shadow-none
        ${paddings[padding]}
        ${hover ? 'transition-all duration-200 hover:border-heal-blue/40 dark:hover:border-blue-500/30 hover:bg-slate-50/50 dark:hover:bg-[#131316]/50' : ''}
        ${className}
      `}
    >
      {children}
    </div>
  );
}
