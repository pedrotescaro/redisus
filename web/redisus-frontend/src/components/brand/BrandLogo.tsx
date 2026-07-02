interface BrandLogoProps {
  compact?: boolean;
  className?: string;
}

export function BrandLogo({ compact = false, className = '' }: BrandLogoProps) {
  return (
    <div className={`flex items-center ${className}`}>
      <img
        src="/images/Logo_final_modobranco.png"
        alt="Heal+"
        className="h-11 w-auto object-contain"
        style={{ filter: "drop-shadow(0 2px 4px rgba(0, 0, 0, 0.15))" }}
      />
    </div>
  );
}
