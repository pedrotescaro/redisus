import { Loader2 } from 'lucide-react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface SocialLoginButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: ReactNode;
  isLoading?: boolean;
}

export function SocialLoginButton({ icon, isLoading, children, disabled, className = '', ...props }: SocialLoginButtonProps) {
  return (
    <button
      type="button"
      className={`inline-flex min-h-11 w-full items-center justify-center gap-3 rounded-xl border border-heal-line bg-white px-4 py-2 text-sm font-bold text-heal-ink transition hover:-translate-y-0.5 hover:border-heal-blue hover:bg-heal-softBlue focus:outline-none focus:ring-2 focus:ring-heal-blue/30 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-950 dark:text-white dark:hover:bg-blue-950/30 ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}
