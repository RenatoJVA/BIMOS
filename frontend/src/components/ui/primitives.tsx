import type { ReactNode } from 'react';

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className = 'w-full h-4' }: SkeletonProps) {
  return (
    <div className={`animate-pulse rounded-md bg-bg-card-hover ${className}`} aria-hidden="true" />
  );
}

export function PanelLabel({ children }: { children: ReactNode }) {
  return (
    <div className="text-[0.7rem] uppercase tracking-widest text-text-secondary font-mono mb-2">
      {children}
    </div>
  );
}