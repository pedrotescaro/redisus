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
        bg-white dark:bg-zinc-900
        border border-heal-line dark:border-zinc-800
        rounded-2xl shadow-soft
        ${paddings[padding]}
        ${hover ? 'transition-all duration-200 hover:shadow-md hover:-translate-y-0.5 hover:border-heal-blue/20' : ''}
        ${className}
      `}
    >
      {children}
    </div>
  );
}
