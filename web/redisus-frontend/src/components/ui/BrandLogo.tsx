import iconUrl from '../../assets/brand/icon.png';

interface BrandLogoProps {
  className?: string;
  showText?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const sizes = {
  sm: { icon: 'w-8 h-8', title: 'text-lg', sub: 'text-[0.6rem]' },
  md: { icon: 'w-10 h-10', title: 'text-xl', sub: 'text-[0.65rem]' },
  lg: { icon: 'w-14 h-14', title: 'text-2xl', sub: 'text-xs' },
};

export function BrandLogo({ className = '', showText = true, size = 'md' }: BrandLogoProps) {
  const s = sizes[size];

  return (
    <div className={`flex items-center gap-3 select-none ${className}`}>
      <div className={`${s.icon} shrink-0 rounded-xl overflow-hidden shadow-soft ring-1 ring-heal-line/50`}>
        <img
          src={iconUrl}
          alt="Heal+"
          className="w-full h-full object-contain"
          draggable={false}
        />
      </div>
      {showText && (
        <div className="flex flex-col min-w-0">
          <span className={`${s.title} font-extrabold text-heal-ink dark:text-white leading-none tracking-tight`}>
            Heal<span className="text-heal-blue">+</span>
          </span>
          <span className={`${s.sub} font-semibold text-heal-teal uppercase tracking-widest leading-none mt-1`}>
            Cuidado Inteligente
          </span>
        </div>
      )}
    </div>
  );
}
