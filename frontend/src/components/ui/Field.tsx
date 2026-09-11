import type { ReactNode } from 'react';

interface FieldProps {
  label: string;
  htmlFor: string;
  hint?: string;
  error?: string | null;
  children: ReactNode;
}

export function Field({ label, htmlFor, hint, error, children }: FieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={htmlFor} className="font-mono text-[0.7rem] uppercase tracking-widest text-text-secondary">
        {label}
      </label>
      {children}
      {error ? (
        <p className="text-[0.72rem] font-mono text-danger" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="text-[0.72rem] font-mono text-text-secondary opacity-70">{hint}</p>
      ) : null}
    </div>
  );
}

export const inputClass =
  'bg-bg-card border border-border text-text-primary px-3 py-2 font-mono text-[0.85rem] rounded-md focus:outline-none focus:border-accent focus:bg-bg-card-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent transition-all';