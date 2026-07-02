interface BrandLogoProps {
  className?: string;
  showText?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const sizes = {
  sm: 'h-8',
  md: 'h-11',
  lg: 'h-16',
};

export function BrandLogo({ className = '', showText = true, size = 'md' }: BrandLogoProps) {
  const heightClass = sizes[size];

  return (
    <div className={`flex items-center select-none ${className}`}>
      <img
        src="/images/Logo_final_modobranco.png"
        alt="Heal+"
        className={`${heightClass} w-auto object-contain`}
        draggable={false}
        style={{ filter: "drop-shadow(0 2px 4px rgba(0, 0, 0, 0.15))" }}
      />
    </div>
  );
}
