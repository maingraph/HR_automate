/**
 * Input component - Executive Talent Engine Design System
 * 
 * Form inputs with white background and Slate borders.
 * Focus state: Deep Indigo border with subtle glow.
 */

import { InputHTMLAttributes, forwardRef, ReactNode } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  icon?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, icon, className = '', ...props }, ref) => {
    return (
      <div className="space-y-1">
        {label && (
          <label className="block font-label text-label-sm text-on-surface">
            {label}
          </label>
        )}
        <div className="relative">
          {icon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant">
              {icon}
            </div>
          )}
          <input
            ref={ref}
            className={`
              w-full bg-surface-container-lowest border rounded-lg px-3 py-2
              font-body text-body-md text-on-surface placeholder:text-outline
              transition-all
              ${error ? 'border-error focus:border-error focus:ring-2 focus:ring-error/20' : 'border-outline-variant focus:border-primary focus:ring-2 focus:ring-primary/20'}
              ${icon ? 'pl-10' : ''}
              ${className}
            `}
            {...props}
          />
        </div>
        {error && (
          <p className="text-label-sm text-error flex items-center gap-1">
            <span className="material-symbols-outlined text-[14px]">error</span>
            {error}
          </p>
        )}
        {helperText && !error && (
          <p className="text-label-sm text-on-surface-variant">{helperText}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';

/**
 * Textarea component
 */
interface TextareaProps extends InputHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helperText?: string;
  rows?: number;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, helperText, rows = 4, className = '', ...props }, ref) => {
    return (
      <div className="space-y-1">
        {label && (
          <label className="block font-label text-label-sm text-on-surface">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          rows={rows}
          className={`
            w-full bg-surface-container-lowest border rounded-lg px-3 py-2
            font-body text-body-md text-on-surface placeholder:text-outline
            transition-all resize-y
            ${error ? 'border-error focus:border-error focus:ring-2 focus:ring-error/20' : 'border-outline-variant focus:border-primary focus:ring-2 focus:ring-primary/20'}
            ${className}
          `}
          {...props}
        />
        {error && (
          <p className="text-label-sm text-error flex items-center gap-1">
            <span className="material-symbols-outlined text-[14px]">error</span>
            {error}
          </p>
        )}
        {helperText && !error && (
          <p className="text-label-sm text-on-surface-variant">{helperText}</p>
        )}
      </div>
    );
  }
);

Textarea.displayName = 'Textarea';

/**
 * Select component
 */
interface SelectProps extends InputHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  helperText?: string;
  options: { value: string; label: string }[];
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, helperText, options, className = '', ...props }, ref) => {
    return (
      <div className="space-y-1">
        {label && (
          <label className="block font-label text-label-sm text-on-surface">
            {label}
          </label>
        )}
        <div className="relative">
          <select
            ref={ref}
            className={`
              w-full bg-surface-container-lowest border rounded-lg px-3 py-2 pr-10
              font-body text-body-md text-on-surface
              transition-all appearance-none cursor-pointer
              ${error ? 'border-error focus:border-error focus:ring-2 focus:ring-error/20' : 'border-outline-variant focus:border-primary focus:ring-2 focus:ring-primary/20'}
              ${className}
            `}
            {...props}
          >
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-on-surface-variant pointer-events-none">
            expand_more
          </span>
        </div>
        {error && (
          <p className="text-label-sm text-error flex items-center gap-1">
            <span className="material-symbols-outlined text-[14px]">error</span>
            {error}
          </p>
        )}
        {helperText && !error && (
          <p className="text-label-sm text-on-surface-variant">{helperText}</p>
        )}
      </div>
    );
  }
);

Select.displayName = 'Select';
