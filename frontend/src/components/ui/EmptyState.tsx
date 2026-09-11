import type { ReactNode } from 'react';

interface EmptyStateProps {
  title: string;
  hint?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
}

export function EmptyState({ title, hint, icon, action }: EmptyStateProps) {
  return (
    <div className="bg-bg-card/30 border border-dashed border-border rounded-lg px-8 py-16 text-center text-text-secondary font-mono flex flex-col items-center gap-4 animate-fadeIn">
      {icon && <div className="text-text-secondary opacity-60 text-3xl">{icon}</div>}
      <p className="text-sm">{title}</p>
      {hint && <div className="text-xs opacity-70 max-w-md leading-relaxed">{hint}</div>}
      {action && <div>{action}</div>}
    </div>
  );
}