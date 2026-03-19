import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost" | "outline";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
};

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-primary-gradient text-white hover:opacity-90 shadow-ambient",
  secondary:
    "bg-surface-container text-on-surface hover:bg-surface-container-high",
  danger: "bg-error text-on-error hover:bg-error/90",
  ghost: "bg-transparent text-primary hover:bg-primary/10",
  outline:
    "bg-transparent border border-outline-variant/30 text-on-surface hover:bg-surface-container hover:border-primary/30",
};

export function Button({
  className = "",
  variant = "primary",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-all disabled:cursor-not-allowed disabled:opacity-50",
        variantClasses[variant],
        className
      )}
      {...props}
    />
  );
}
