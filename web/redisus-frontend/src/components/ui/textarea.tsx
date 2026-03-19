import type { TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement>;

export function Textarea({ className = "", ...props }: TextareaProps) {
  return (
    <textarea
      className={cn(
        "w-full rounded-xl border border-outline-variant/15 bg-surface-container-high px-4 py-2.5 text-sm text-on-surface outline-none transition-all placeholder:text-gray-500 focus:border-primary focus:ring-2 focus:ring-primary/20 resize-none",
        className
      )}
      {...props}
    />
  );
}
