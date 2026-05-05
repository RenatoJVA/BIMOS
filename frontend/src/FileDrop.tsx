import { useState, useRef } from 'react';

interface FileDropProps {
  label: string;
  accept?: string;
  onFileSelect: (file: File | null) => void;
  file: File | null;
}

export function FileDrop({ label, accept, onFileSelect, file }: FileDropProps) {
  const [isOver, setIsOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsOver(false);
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) onFileSelect(droppedFile);
  };

  return (
    <div 
      className={`w-full border-dashed p-6 rounded-lg text-center cursor-pointer transition-all duration-200 relative bg-bg-card border ${
        isOver ? 'border-accent bg-bg-card-hover' : 
        file ? 'border-success border-solid' : 'border-border'
      } hover:border-accent hover:bg-bg-card-hover`}
      onDragOver={(e) => { e.preventDefault(); setIsOver(true); }}
      onDragLeave={() => setIsOver(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input 
        type="file" 
        ref={inputRef}
        accept={accept}
        className="hidden"
        onChange={(e) => onFileSelect(e.target.files?.[0] || null)}
      />
      <div className="flex flex-col gap-1">
        <span className="text-[0.7rem] font-mono text-text-secondary uppercase tracking-widest">{label}</span>
        <span className="text-[0.8rem] text-text-primary font-medium truncate px-4">
          {file ? file.name : 'Drag & drop or click to upload'}
        </span>
      </div>
      {file && (
        <button 
          className="absolute top-1 right-1 bg-transparent border-none text-text-secondary text-lg cursor-pointer p-1 hover:text-danger" 
          onClick={(e) => { e.stopPropagation(); onFileSelect(null); }}
        >
          &times;
        </button>
      )}
    </div>
  );
}
