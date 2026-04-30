import logoUrl from '../../assets/brand/logo.png';

interface BrandLogoProps {
  compact?: boolean;
  className?: string;
}

export function BrandLogo({ compact = false, className = '' }: BrandLogoProps) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-heal-line">
        <img src={logoUrl} alt="Heal+" className="h-9 w-9 object-contain" />
      </div>
      {!compact ? (
        <div className="min-w-0">
          <div className="text-xl font-black leading-tight text-heal-ink dark:text-white">
            Heal<span className="text-heal-blue">+</span>
          </div>
          <div className="text-xs font-semibold text-heal-muted dark:text-zinc-400">Cuidado inteligente</div>
        </div>
      ) : null}
    </div>
  );
}
