/**
 * Skeleton loader component for loading states.
 * 
 * Usage:
 *   <Skeleton className="h-8 w-64" />
 *   <Skeleton variant="card" />
 */

interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'card' | 'circle' | 'button';
}

export function Skeleton({ className = '', variant = 'text' }: SkeletonProps) {
  const baseClasses = 'animate-pulse bg-[var(--border)] rounded';
  
  const variantClasses = {
    text: 'h-4 w-full',
    card: 'h-32 w-full',
    circle: 'h-12 w-12 rounded-full',
    button: 'h-10 w-24',
  };
  
  const classes = `${baseClasses} ${variantClasses[variant]} ${className}`;
  
  return <div className={classes} />;
}

/**
 * Skeleton for candidate card
 */
export function CandidateSkeleton() {
  return (
    <div className="border border-[var(--border)] rounded-lg p-4 space-y-3">
      <div className="flex items-center gap-3">
        <Skeleton variant="circle" className="h-10 w-10" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-4 w-64" />
        </div>
      </div>
      <div className="flex gap-2">
        <Skeleton className="h-6 w-16" />
        <Skeleton className="h-6 w-20" />
        <Skeleton className="h-6 w-24" />
      </div>
    </div>
  );
}

/**
 * Skeleton for job card
 */
export function JobSkeleton() {
  return (
    <div className="border border-[var(--border)] rounded-lg p-6 space-y-4">
      <div className="flex items-start justify-between">
        <div className="space-y-2 flex-1">
          <Skeleton className="h-6 w-64" />
          <Skeleton className="h-4 w-32" />
        </div>
        <Skeleton variant="button" />
      </div>
      <div className="grid grid-cols-4 gap-4">
        <Skeleton variant="card" className="h-20" />
        <Skeleton variant="card" className="h-20" />
        <Skeleton variant="card" className="h-20" />
        <Skeleton variant="card" className="h-20" />
      </div>
    </div>
  );
}

/**
 * Skeleton for table rows
 */
export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 p-3 border border-[var(--border)] rounded">
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-4 flex-1" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-16" />
        </div>
      ))}
    </div>
  );
}
