import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type InputProps = InputHTMLAttributes<HTMLInputElement>;

export function Input({ className = "", ...props }: InputProps) {
  return (
    <input
      className={cn(
        "w-full rounded-xl border border-outline-variant/15 bg-surface-container-high px-4 py-2.5 text-sm text-on-surface outline-none transition-all placeholder:text-gray-500 focus:border-primary focus:ring-2 focus:ring-primary/20",
        className
      )}
      {...props}
    />
  );
}
