import React, { forwardRef } from 'react';

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options: ReadonlyArray<string | { value: string; label: string }>;
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, options, placeholder, className = '', id, ...props }, ref) => {
    const selectId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

    return (
      <div className={className}>
        {label && (
          <label
            htmlFor={selectId}
            className="block text-sm font-semibold text-heal-ink dark:text-white mb-1.5"
          >
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          className={`
            block w-full rounded-xl border bg-white
            text-sm text-heal-ink
            transition-colors duration-150
            focus:outline-none focus:ring-2 focus:ring-heal-blue/20 focus:border-heal-blue
            disabled:opacity-50 disabled:bg-slate-100 disabled:cursor-not-allowed
            dark:bg-zinc-900 dark:text-white dark:border-zinc-700
            dark:focus:ring-heal-blue/30 dark:focus:border-heal-blue
            ${error ? 'border-heal-danger focus:ring-heal-danger/20 focus:border-heal-danger' : 'border-heal-line'}
            h-11 px-3.5
          `}
          {...props}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map(opt => {
            const value = typeof opt === 'string' ? opt : opt.value;
            const label = typeof opt === 'string' ? opt : opt.label;
            return (
            <option key={value} value={value}>
              {label}
            </option>
            );
          })}
        </select>
        {error && (
          <p className="mt-1.5 text-xs font-medium text-heal-danger">{error}</p>
        )}
      </div>
    );
  }
);

Select.displayName = 'Select';
