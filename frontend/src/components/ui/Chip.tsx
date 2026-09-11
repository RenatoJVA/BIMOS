import type { ReactNode } from 'react';

interface ChipProps {
  children: ReactNode;
  variant?: 'default' | 'accent' | 'success' | 'warning' | 'danger';
  title?: string;
}

const VARIANT: Record<string, string> = {
  default: 'border-border text-text-secondary',
  accent: 'border-accent text-accent',
  success: 'border-success text-success',
  warning: 'border-warning text-warning',
  danger: 'border-danger text-danger',
};

export function Chip({ children, variant = 'default', title }: ChipProps) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 text-[0.7rem] font-mono px-2 py-0.5 rounded-[4px] border ${VARIANT[variant]}`}
    >
      {children}
    </span>
  );
}