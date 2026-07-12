interface ProgressBarProps {
  current: number;
  total: number;
  percentage?: number;
  label?: string;
  message?: string;
  variant?: 'primary' | 'success' | 'warning';
  showPercentage?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export function ProgressBar({
  current,
  total,
  percentage,
  label,
  message,
  variant = 'primary',
  showPercentage = true,
  size = 'md'
}: ProgressBarProps) {
  const pct = percentage ?? (total > 0 ? (current / total * 100) : 0);
  
  const heightClass = size === 'sm' ? 'h-1' : size === 'md' ? 'h-2' : 'h-3';
  
  const colorClass = 
    variant === 'success' ? 'bg-[var(--green)]' :
    variant === 'warning' ? 'bg-yellow-500' :
    'bg-[var(--accent)]';
  
  return (
    <div className="space-y-1">
      {(label || message) && (
        <div className="flex items-center justify-between text-xs">
          {label && <span className="text-[var(--fg2)] font-medium">{label}</span>}
          {message && <span className="text-[var(--muted)]">{message}</span>}
        </div>
      )}
      
      <div className={`relative w-full bg-[var(--panel2)] rounded-full overflow-hidden ${heightClass}`}>
        <div 
          className={`absolute top-0 left-0 h-full transition-all duration-300 ease-out ${colorClass}`}
          style={{ width: `${Math.min(Math.max(pct, 0), 100)}%` }}
        />
      </div>
      
      {showPercentage && (
        <div className="text-xs text-[var(--muted)] text-right">
          {current}/{total} ({pct.toFixed(1)}%)
        </div>
      )}
    </div>
  );
}
