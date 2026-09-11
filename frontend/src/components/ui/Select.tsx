import { useEffect, useId, useRef, useState } from 'react';

interface SelectOption<T extends string> {
  value: T;
  label: string;
}

interface SelectProps<T extends string> {
  value: T;
  options: SelectOption<T>[];
  onChange: (value: T) => void;
  label: string;
}

export function Select<T extends string>({ value, options, onChange, label }: SelectProps<T>) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const listboxId = useId();
  const current = options.find((o) => o.value === value);
  const selectedIndex = options.findIndex((o) => o.value === value);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const moveSelection = (dir: -1 | 1) => {
    if (options.length === 0) return;
    const next = (selectedIndex + dir + options.length) % options.length;
    onChange(options[next].value);
  };

  return (
    <div ref={rootRef} className="relative inline-block">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listboxId}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setOpen((v) => !v);
          }
          if (open) {
            if (e.key === 'ArrowDown' || e.key === 'ArrowRight') {
              e.preventDefault();
              moveSelection(1);
            } else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
              e.preventDefault();
              moveSelection(-1);
            }
          }
        }}
        className={`flex items-center gap-2 border rounded-md bg-bg-card px-3 py-2 font-mono text-[0.8rem] text-text-primary transition-colors cursor-pointer ${
          open ? 'border-accent' : 'border-border hover:border-border-active'
        } focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent`}
      >
        <span>{current?.label ?? label}</span>
        <span
          aria-hidden="true"
          className={`text-text-secondary transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
        >
          ▾
        </span>
      </button>

      {open && (
        <ul
          id={listboxId}
          role="listbox"
          aria-label={label}
          className="absolute left-0 top-full mt-1 z-[100] min-w-[160px] bg-bg-card border border-border rounded-md shadow-lg py-1 custom-scrollbar"
        >
          {options.map((opt) => (
            <li
              key={opt.value}
              role="option"
              aria-selected={opt.value === value}
              onClick={() => {
                onChange(opt.value);
                setOpen(false);
              }}
              className={`px-3 py-1.5 text-[0.8rem] font-mono cursor-pointer transition-colors list-none ${
                opt.value === value
                  ? 'bg-accent-glow text-text-primary font-semibold'
                  : 'text-text-secondary hover:bg-bg-card-hover hover:text-text-primary'
              }`}
            >
              {opt.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}