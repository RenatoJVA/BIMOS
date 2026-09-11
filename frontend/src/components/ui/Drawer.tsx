import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  maxWidth?: string;
}

export function Drawer({ open, onClose, title, children, footer, maxWidth = '640px' }: DrawerProps) {
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    // Focus the panel so keyboard users land inside the drawer.
    const focusTarget = panelRef.current?.querySelector<HTMLElement>('[data-autofocus]');
    (focusTarget ?? panelRef.current)?.focus();
    // Prevent background scroll.
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[1000] flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-label={typeof title === 'string' ? title : 'Job details'}
    >
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        ref={panelRef}
        tabIndex={-1}
        className={`relative flex flex-col h-full border-l border-border bg-bg-card shadow-2xl animate-[slideIn_0.25s_ease-out] focus-visible:outline-none`}
        style={{ width: '100%', maxWidth }}
      >
        <header className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
          <div className="min-w-0 flex-1">{title}</div>
          <button
            onClick={onClose}
            aria-label="Close panel"
            className="shrink-0 bg-transparent border-none text-2xl leading-none text-text-secondary hover:text-text-primary cursor-pointer transition-colors focus-visible:outline focus-visible:outline-accent"
          >
            ×
          </button>
        </header>
        <div className="flex-1 overflow-y-auto custom-scrollbar px-5 py-4">{children}</div>
        {footer && (
          <footer className="border-t border-border px-5 py-3 bg-bg-page/40">{footer}</footer>
        )}
      </aside>
    </div>
  );
}