import type { ReactNode } from 'react';

interface FeatureCardProps {
  icon: ReactNode;
  title: string;
  description: string;
}

export function FeatureCard({ icon, title, description }: FeatureCardProps) {
  return (
    <div className="rounded-card border border-heal-line bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-heal-blue/40 hover:shadow-soft dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue">{icon}</div>
      <h3 className="mt-4 text-sm font-black text-heal-ink dark:text-white">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-heal-muted dark:text-zinc-400">{description}</p>
    </div>
  );
}
