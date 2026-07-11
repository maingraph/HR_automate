/**
 * Button component - Executive Talent Engine Design System
 * 
 * Variants:
 * - primary: Deep Indigo, high-contrast (main actions)
 * - secondary: Ghost style with Slate borders
 * - success: Emerald Green (hire, approve actions)
 * - error: Red (delete, cancel actions)
 */

import { ButtonHTMLAttributes, forwardRef } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'success' | 'error';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', loading, disabled, children, className = '', ...props }, ref) => {
    const baseClasses = 'inline-flex items-center justify-center gap-2 font-label font-semibold rounded-lg transition-all duration-200 ease-in-out active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed';
    
    const variantClasses = {
      primary: 'bg-primary text-on-primary hover:bg-surface-tint focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2',
      secondary: 'bg-transparent border border-outline text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface',
      success: 'bg-tertiary-container text-on-tertiary-container hover:bg-tertiary hover:text-on-tertiary',
      error: 'bg-error text-on-error hover:bg-error/90',
    };
    
    const sizeClasses = {
      sm: 'px-3 py-1.5 text-label-sm',
      md: 'px-4 py-2 text-label-sm',
      lg: 'px-6 py-3 text-body-md',
    };
    
    const classes = `${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`;
    
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={classes}
        {...props}
      >
        {loading && (
          <span className="material-symbols-outlined animate-spin text-[18px]">
            progress_activity
          </span>
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
