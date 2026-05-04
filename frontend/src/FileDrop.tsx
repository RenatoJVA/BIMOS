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
      className={`file-drop ${isOver ? 'drag-over' : ''} ${file ? 'has-file' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setIsOver(true); }}
      onDragLeave={() => setIsOver(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input 
        type="file" 
        ref={inputRef}
        accept={accept}
        style={{ display: 'none' }}
        onChange={(e) => onFileSelect(e.target.files?.[0] || null)}
      />
      <div className="file-drop-content">
        <span className="file-drop-label">{label}</span>
        <span className="file-drop-status">
          {file ? file.name : 'Drag & drop or click to upload'}
        </span>
      </div>
      {file && (
        <button 
          className="file-remove" 
          onClick={(e) => { e.stopPropagation(); onFileSelect(null); }}
        >
          &times;
        </button>
      )}
    </div>
  );
}
