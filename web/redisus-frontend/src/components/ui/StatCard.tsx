import type { ReactNode } from 'react';

type Tone = 'blue' | 'teal' | 'green' | 'amber' | 'slate';

const toneClasses: Record<Tone, string> = {
  blue: 'bg-heal-softBlue text-heal-blue',
  teal: 'bg-heal-tealSoft text-heal-teal',
  green: 'bg-emerald-50 text-heal-success',
  amber: 'bg-amber-50 text-heal-warning',
  slate: 'bg-slate-100 text-slate-600'
};

interface StatCardProps {
  label: string;
  value: number | string;
  icon: ReactNode;
  tone?: Tone;
  hint?: string;
}

export function StatCard({ label, value, icon, tone = 'blue', hint }: StatCardProps) {
  return (
    <div className="rounded-card border border-heal-line bg-white p-5 shadow-soft transition hover:-translate-y-0.5 hover:border-heal-blue/40 dark:border-zinc-800 dark:bg-zinc-900">
      <div className={`mb-5 flex h-12 w-12 items-center justify-center rounded-2xl ${toneClasses[tone]}`}>{icon}</div>
      <p className="text-3xl font-black tracking-tight text-heal-ink dark:text-white">{value}</p>
      <p className="mt-1 text-sm font-bold text-heal-muted dark:text-zinc-400">{label}</p>
      {hint ? <p className="mt-3 text-xs leading-5 text-slate-500 dark:text-zinc-500">{hint}</p> : null}
    </div>
  );
}
