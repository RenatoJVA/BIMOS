import { useRef, useState } from 'react';

interface FileDropProps {
  id: string;
  label: string;
  accept?: string;
  onFileSelect: (file: File | null) => void;
  file: File | null;
}

function extension(file: File): string {
  return file.name.includes('.') ? file.name.slice(file.name.lastIndexOf('.')).toLowerCase() : '';
}

function matchesAccept(file: File, accept?: string): boolean {
  if (!accept) return true;
  return accept.split(',').some((token) => token.trim().toLowerCase() === extension(file));
}

export function FileDrop({ id, label, accept, onFileSelect, file }: FileDropProps) {
  const [isOver, setIsOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (candidate?: File) => {
    if (!candidate) return;
    if (accept && !matchesAccept(candidate, accept)) {
      setError(`Expected ${accept} file, got ${extension(candidate) || candidate.type || 'unknown'}`);
      return;
    }
    setError(null);
    onFileSelect(candidate);
  };

  return (
    <div
      className={`w-full border-dashed p-6 rounded-lg text-center cursor-pointer transition-all duration-200 relative bg-bg-card border ${
        isOver
          ? 'border-accent bg-bg-card-hover'
          : error
            ? 'border-danger'
            : file
              ? 'border-success border-solid'
              : 'border-border'
      } hover:border-accent hover:bg-bg-card-hover`}
      onDragOver={(e) => {
        e.preventDefault();
        setIsOver(true);
      }}
      onDragLeave={() => setIsOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsOver(false);
        handleFile(e.dataTransfer.files?.[0]);
      }}
      onClick={() => inputRef.current?.click()}
    >
      <input
        id={id}
        ref={inputRef}
        type="file"
        accept={accept}
        className="sr-only"
        onChange={(e) => handleFile(e.target.files?.[0] || undefined)}
      />
      <div className="flex flex-col gap-1">
        <label
          htmlFor={id}
          onClick={(e) => e.stopPropagation()}
          className="text-[0.7rem] font-mono text-text-secondary uppercase tracking-widest cursor-pointer"
        >
          {label}
        </label>
        <span className="text-[0.8rem] text-text-primary font-medium truncate px-4">
          {file ? file.name : 'Drag & drop or click to upload'}
        </span>
        {file && (
          <span className="text-[0.65rem] text-text-secondary opacity-70">
            {file.size >= 1024 * 1024
              ? `${(file.size / (1024 * 1024)).toFixed(1)} MB`
              : `${Math.max(1, Math.round(file.size / 1024))} KB`}
            {accept ? ` — ${accept.split(',').join(' or ')}` : ''}
          </span>
        )}
        {error && <span className="text-[0.7rem] font-mono text-danger mt-1">{error}</span>}
      </div>
      {file && (
        <button
          aria-label={`Remove ${label}`}
          className="absolute top-1 right-1 bg-transparent border-none text-text-secondary text-lg cursor-pointer p-1 hover:text-danger focus-visible:outline focus-visible:outline-accent"
          onClick={(e) => {
            e.stopPropagation();
            setError(null);
            onFileSelect(null);
          }}
        >
          ×
        </button>
      )}
    </div>
  );
}