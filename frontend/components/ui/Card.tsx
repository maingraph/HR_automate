/**
 * Card component - Executive Talent Engine Design System
 * 
 * Primary container for candidate profiles, job cards, and dashboard widgets.
 * Features 1px border with subtle hover effects.
 */

import { HTMLAttributes, forwardRef } from 'react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  interactive?: boolean;
  padding?: 'sm' | 'md' | 'lg';
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ interactive, padding = 'md', className = '', children, ...props }, ref) => {
    const baseClasses = 'bg-[var(--panel)] border border-[var(--border)] rounded-xl transition-colors';
    const interactiveClasses = interactive ? 'cursor-pointer hover:border-[var(--accent)]/30 hover:shadow-lg' : '';
    
    const paddingClasses = {
      sm: 'p-sm',
      md: 'p-md',
      lg: 'p-lg',
    };
    
    const classes = `${baseClasses} ${interactiveClasses} ${paddingClasses[padding]} ${className}`;
    
    return (
      <div ref={ref} className={classes} {...props}>
        {children}
      </div>
    );
  }
);

Card.displayName = 'Card';

/**
 * Card Header - for titles and actions
 */
export function CardHeader({ className = '', children }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`flex items-start justify-between mb-md ${className}`}>
      {children}
    </div>
  );
}

/**
 * Card Title
 */
export function CardTitle({ className = '', children }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className={`font-title text-title-sm text-[var(--fg)] ${className}`}>
      {children}
    </h3>
  );
}

/**
 * Card Content
 */
export function CardContent({ className = '', children }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`space-y-sm ${className}`}>
      {children}
    </div>
  );
}

/**
 * Card Footer - for actions
 */
export function CardFooter({ className = '', children }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`flex items-center gap-2 mt-md pt-md border-t border-[var(--border)] ${className}`}>
      {children}
    </div>
  );
}
