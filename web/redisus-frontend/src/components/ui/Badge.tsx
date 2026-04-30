import React from 'react';

type BadgeTone = 'blue' | 'green' | 'red' | 'amber' | 'slate' | 'teal' | 'purple';

interface BadgeProps {
  children: React.ReactNode;
  tone?: BadgeTone;
  className?: string;
  dot?: boolean;
}

const toneStyles: Record<BadgeTone, string> = {
  blue: 'bg-heal-softBlue text-heal-blue dark:bg-blue-950/40 dark:text-blue-300',
  green: 'bg-heal-successSoft text-green-700 dark:bg-green-950/40 dark:text-green-300',
  red: 'bg-heal-dangerSoft text-red-700 dark:bg-red-950/40 dark:text-red-300',
  amber: 'bg-heal-warningSoft text-amber-700 dark:bg-amber-950/40 dark:text-amber-300',
  slate: 'bg-gray-100 text-gray-600 dark:bg-zinc-800 dark:text-zinc-400',
  teal: 'bg-heal-tealSoft text-heal-tealDark dark:bg-teal-950/40 dark:text-teal-300',
  purple: 'bg-purple-50 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300',
};

const dotColors: Record<BadgeTone, string> = {
  blue: 'bg-heal-blue',
  green: 'bg-heal-success',
  red: 'bg-heal-danger',
  amber: 'bg-heal-warning',
  slate: 'bg-gray-400',
  teal: 'bg-heal-teal',
  purple: 'bg-purple-500',
};

export function Badge({ children, tone = 'blue', className = '', dot = false }: BadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center gap-1.5
        px-2.5 py-0.5
        text-xs font-semibold
        rounded-full
        ${toneStyles[tone]}
        ${className}
      `}
    >
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${dotColors[tone]}`} />}
      {children}
    </span>
  );
}
