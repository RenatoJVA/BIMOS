import { useCallback, useRef, useState } from 'react';

interface CopyButtonProps {
  value: string;
  label?: string;
  className?: string;
}

export function CopyButton({ value, label = 'Copy', className = '' }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | null>(null);

  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard unavailable (non-secure context) — leave state */
    }
  }, [value]);

  return (
    <button
      onClick={copy}
      aria-label={`${copied ? 'Copied' : 'Copy'} ${label}`}
      title={value}
      className={`inline-flex items-center gap-1 text-[0.7rem] font-mono uppercase tracking-wider px-2 py-0.5 rounded border border-border text-text-secondary hover:text-accent hover:border-accent transition-colors cursor-pointer focus-visible:outline focus-visible:outline-accent ${
        copied ? 'text-success border-success' : ''
      } ${className}`}
    >
      {copied ? 'Copied' : label}
    </button>
  );
}