import type { ReactNode } from 'react';

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function PageHeader({ eyebrow, title, description, action }: PageHeaderProps) {
  return (
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div className="max-w-3xl">
        {eyebrow ? <p className="text-xs font-black uppercase tracking-[0.18em] text-heal-teal">{eyebrow}</p> : null}
        <h1 className="mt-1 text-2xl font-black tracking-tight text-heal-ink dark:text-white md:text-3xl">{title}</h1>
        {description ? <p className="mt-2 text-sm leading-6 text-heal-muted dark:text-zinc-400">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
