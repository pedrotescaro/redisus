import React, { forwardRef } from 'react';

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, helperText, className = '', id, ...props }, ref) => {
    const textareaId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

    return (
      <div className={className}>
        {label && (
          <label
            htmlFor={textareaId}
            className="block text-sm font-semibold text-heal-ink dark:text-white mb-1.5"
          >
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={textareaId}
          className={`
            block w-full rounded-xl border bg-white
            text-sm text-heal-ink placeholder:text-heal-mutedLight
            transition-colors duration-150
            focus:outline-none focus:ring-2 focus:ring-heal-blue/20 focus:border-heal-blue
            disabled:opacity-50 disabled:bg-heal-surfaceHover disabled:cursor-not-allowed
            dark:bg-zinc-900 dark:text-white dark:border-zinc-700
            dark:placeholder:text-zinc-500 dark:focus:ring-heal-blue/30 dark:focus:border-heal-blue
            ${error ? 'border-heal-danger focus:ring-heal-danger/20 focus:border-heal-danger' : 'border-heal-line'}
            px-3.5 py-3 min-h-[100px] resize-y
          `}
          {...props}
        />
        {error && (
          <p className="mt-1.5 text-xs font-medium text-heal-danger">{error}</p>
        )}
        {helperText && !error && (
          <p className="mt-1.5 text-xs text-heal-muted">{helperText}</p>
        )}
      </div>
    );
  }
);

Textarea.displayName = 'Textarea';
