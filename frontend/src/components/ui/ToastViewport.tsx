import type { ToastItem } from '../../hooks/useToast';

export function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}) {
  return (
    <div
      className="fixed bottom-4 right-4 z-[1200] flex flex-col gap-2 w-[360px] max-w-[calc(100vw-2rem)]"
      role="status"
      aria-live="polite"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`animate-fadeIn flex items-start justify-between gap-3 border rounded-lg px-4 py-3 shadow-lg bg-bg-card text-text-primary text-sm font-mono ${
            t.type === 'error'
              ? 'border-danger'
              : t.type === 'success'
                ? 'border-success'
                : 'border-accent'
          }`}
        >
          <span className="leading-snug">{t.message}</span>
          <button
            onClick={() => onDismiss(t.id)}
            aria-label="Dismiss notification"
            className="text-text-secondary hover:text-text-primary cursor-pointer bg-transparent border-none shrink-0 focus-visible:outline focus-visible:outline-accent"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}