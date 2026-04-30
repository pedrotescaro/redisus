import React from 'react';
import { Loader2 } from 'lucide-react';

interface SocialLoginButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  provider: 'google' | 'microsoft' | 'apple';
  icon?: React.ReactNode;
  isLoading?: boolean;
}

const providerLabels: Record<string, string> = {
  google: 'Continuar com Google',
  microsoft: 'Continuar com Microsoft',
  apple: 'Continuar com Apple',
};

export function SocialLoginButton({
  provider,
  icon,
  isLoading,
  children,
  ...props
}: SocialLoginButtonProps) {
  const label = children || providerLabels[provider];

  return (
    <button
      type="button"
      className={`
        w-full flex items-center justify-center gap-3
        px-4 py-3 h-12
        border border-heal-line
        rounded-xl shadow-sm
        bg-white
        text-sm font-semibold text-heal-ink
        transition-all duration-150 ease-out
        hover:bg-heal-softBlue hover:border-heal-blue/40 hover:shadow-soft
        active:scale-[0.98]
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-heal-blue focus-visible:ring-offset-2
        disabled:opacity-50 disabled:pointer-events-none
      `}
      disabled={isLoading}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="h-5 w-5 animate-spin text-heal-muted" />
      ) : (
        icon && <span className="w-5 h-5 flex items-center justify-center shrink-0">{icon}</span>
      )}
      <span>{label}</span>
    </button>
  );
}
