/**
 * Empty state component for when there's no data.
 * 
 * Usage:
 *   <EmptyState 
 *     icon="📭"
 *     title="No candidates yet"
 *     description="Run the pipeline to start finding candidates"
 *     action={{ label: "Run Pipeline", onClick: () => {} }}
 *   />
 */

interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      {icon && (
        <div className="text-5xl mb-4 opacity-50">
          {icon}
        </div>
      )}
      <h3 className="text-lg font-medium mb-2">{title}</h3>
      {description && (
        <p className="text-sm text-[var(--muted)] mb-6 max-w-md">
          {description}
        </p>
      )}
      {action && (
        <button
          onClick={action.onClick}
          className="px-4 py-2 rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent)]/90 transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}

/**
 * Empty state variants for common scenarios
 */
export function NoCandidatesEmpty({ onRun }: { onRun: () => void }) {
  return (
    <EmptyState
      icon="🔍"
      title="No candidates yet"
      description="Run the sourcing pipeline to start finding and scoring candidates automatically."
      action={{ label: "Launch Pipeline", onClick: onRun }}
    />
  );
}

export function NoJobsEmpty({ onCreate }: { onCreate: () => void }) {
  return (
    <EmptyState
      icon="📋"
      title="No jobs yet"
      description="Create your first sourcing job to get started with AI-powered recruitment."
      action={{ label: "Create Job", onClick: onCreate }}
    />
  );
}

export function NoResultsEmpty() {
  return (
    <EmptyState
      icon="🔎"
      title="No results found"
      description="Try adjusting your filters or search criteria."
    />
  );
}

export function ErrorEmpty({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <EmptyState
      icon="⚠️"
      title="Something went wrong"
      description={error}
      action={onRetry ? { label: "Try Again", onClick: onRetry } : undefined}
    />
  );
}
