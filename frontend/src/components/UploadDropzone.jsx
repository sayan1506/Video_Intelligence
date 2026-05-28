import { useState } from 'react';
import { Upload } from 'lucide-react';

/**
 * UploadDropzone — a drag-and-drop zone for video file uploads.
 *
 * Props:
 *   onDragOver  — handler for dragover events
 *   onDrop      — handler for drop events
 *   onClick     — handler for click-to-browse
 *   fileInputRef — ref for the hidden file input
 *   onFileChange — handler for file input change
 *   accept      — accepted file types string
 */
export default function UploadDropzone({ onDragOver, onDrop, onClick, fileInputRef, onFileChange, accept }) {
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
    if (onDragOver) onDragOver(e);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (onDrop) onDrop(e);
  };

  return (
    <div
      className={[
        'border-2 rounded-2xl p-8 sm:p-12 text-center cursor-pointer group transition-all duration-150',
        isDragOver
          ? 'border-solid border-gold-light-accent dark:border-gold-accent bg-[rgba(184,150,12,0.15)] dark:bg-gold-accent-muted'
          : 'border-dashed border-gold-light-accent dark:border-gold-accent',
      ].join(' ')}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={onClick}
    >
      <div className={[
        'w-16 h-16 mx-auto rounded-full flex items-center justify-center mb-4 transition-all duration-150',
        isDragOver
          ? 'bg-[rgba(184,150,12,0.25)] dark:bg-[rgba(212,175,55,0.25)]'
          : 'bg-[rgba(184,150,12,0.08)] dark:bg-[rgba(212,175,55,0.08)]',
      ].join(' ')}>
        <Upload className="w-8 h-8 text-gold-light-accent dark:text-gold-accent" />
      </div>
      <p className="text-lg font-medium text-gold-light-text-primary dark:text-gold-text-primary mb-1">
        Drag & drop your video here
      </p>
      <p className="text-sm text-gold-light-text-muted dark:text-gold-text-muted">or click to browse</p>
      <input
        type="file"
        className="hidden"
        ref={fileInputRef}
        onChange={onFileChange}
        accept={accept}
      />
    </div>
  );
}
