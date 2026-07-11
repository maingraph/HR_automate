/**
 * Badge/Chip component - Executive Talent Engine Design System
 * 
 * Used for candidate tags, status indicators, and labels.
 * Desaturated colors with dark text for readability.
 */

import { HTMLAttributes } from 'react';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'success' | 'error' | 'info' | 'neutral';
  size?: 'sm' | 'md';
}

export function Badge({ variant = 'neutral', size = 'md', className = '', children, ...props }: BadgeProps) {
  const baseClasses = 'inline-flex items-center gap-1 rounded-md font-label';
  
  const variantClasses = {
    success: 'bg-tertiary-container/10 text-on-tertiary-container',
    error: 'bg-error-container/10 text-on-error-container',
    info: 'bg-primary-container/10 text-on-primary-container',
    neutral: 'bg-surface-container text-on-surface-variant',
  };
  
  const sizeClasses = {
    sm: 'px-1.5 py-0.5 text-[10px]',
    md: 'px-2 py-1 text-label-caps',
  };
  
  const classes = `${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`;
  
  return (
    <span className={classes} {...props}>
      {children}
    </span>
  );
}

/**
 * Status Badge with icon
 */
interface StatusBadgeProps extends BadgeProps {
  icon?: string;
  trend?: 'up' | 'down';
}

export function StatusBadge({ icon, trend, children, ...props }: StatusBadgeProps) {
  return (
    <Badge {...props}>
      {trend && (
        <span className="material-symbols-outlined text-[14px]">
          {trend === 'up' ? 'arrow_upward' : 'arrow_downward'}
        </span>
      )}
      {icon && <span className="material-symbols-outlined text-[14px]">{icon}</span>}
      {children}
    </Badge>
  );
}

/**
 * Status Dot - minimal indicator
 */
interface StatusDotProps {
  status: 'success' | 'error' | 'pending' | 'neutral';
  className?: string;
}

export function StatusDot({ status, className = '' }: StatusDotProps) {
  const statusClasses = {
    success: 'bg-on-tertiary-container',
    error: 'bg-error',
    pending: 'bg-outline animate-pulse',
    neutral: 'bg-outline-variant',
  };
  
  return <span className={`w-2 h-2 rounded-full ${statusClasses[status]} ${className}`} />;
}
