/**
 * DITrackUpload - File upload component for DI tracks.
 */
import type React from 'react';
import { useRef, useState, useCallback } from 'react';
import { Upload, X, Music, AlertCircle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface DITrackUploadProps {
  file: File | null;
  onFileSelect: (file: File | null) => void;
  isUploading?: boolean;
  error?: string | null;
  className?: string;
}

const ACCEPTED_FORMATS = ['.wav', '.mp3', '.flac', '.aiff', '.aif'];
const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB

export function DITrackUpload({
  file,
  onFileSelect,
  isUploading = false,
  error,
  className,
}: DITrackUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const validateFile = useCallback((file: File): string | null => {
    const extension = `.${file.name.split('.').pop()?.toLowerCase()}`;
    if (!ACCEPTED_FORMATS.includes(extension)) {
      return `Invalid format. Accepted: ${ACCEPTED_FORMATS.join(', ')}`;
    }
    if (file.size > MAX_FILE_SIZE) {
      return `File too large. Maximum size: ${MAX_FILE_SIZE / 1024 / 1024}MB`;
    }
    return null;
  }, []);

  const handleFile = useCallback(
    (file: File) => {
      const error = validateFile(file);
      if (error) {
        setValidationError(error);
        return;
      }
      setValidationError(null);
      onFileSelect(file);
    },
    [validateFile, onFileSelect]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragOver(false);

      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile) {
        handleFile(droppedFile);
      }
    },
    [handleFile]
  );

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      if (selectedFile) {
        handleFile(selectedFile);
      }
    },
    [handleFile]
  );

  const handleRemove = useCallback(() => {
    onFileSelect(null);
    setValidationError(null);
    if (inputRef.current) {
      inputRef.current.value = '';
    }
  }, [onFileSelect]);

  const displayError = validationError || error;

  return (
    <div className={cn('space-y-2', className)}>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_FORMATS.join(',')}
        onChange={handleInputChange}
        className="hidden"
        disabled={isUploading}
      />

      {file ? (
        // File selected state
        <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-amber-500/20">
            {isUploading ? (
              <Loader2 className="h-5 w-5 animate-spin text-amber-500" />
            ) : (
              <Music className="h-5 w-5 text-amber-500" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium text-foreground">{file.name}</p>
            <p className="text-xs text-muted-foreground">
              {(file.size / 1024 / 1024).toFixed(2)} MB
              {isUploading && ' · Uploading...'}
            </p>
          </div>
          {!isUploading && (
            <button
              onClick={handleRemove}
              className="shrink-0 rounded-full p-1 text-muted-foreground hover:bg-destructive/20 hover:text-destructive"
              aria-label="Remove file"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      ) : (
        // Drop zone state
        <div
          onClick={() => inputRef.current?.click()}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className={cn(
            'flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors',
            isDragOver
              ? 'border-amber-500 bg-amber-500/10'
              : 'border-border hover:border-amber-500/50 hover:bg-muted/50'
          )}
        >
          <Upload
            className={cn(
              'mb-3 h-8 w-8',
              isDragOver ? 'text-amber-500' : 'text-muted-foreground'
            )}
          />
          <p className="text-sm font-medium text-foreground">
            {isDragOver ? 'Drop your DI track here' : 'Upload DI Track'}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Drag & drop or click to browse
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            WAV, MP3, FLAC, AIFF · Max 100MB
          </p>
        </div>
      )}

      {displayError && (
        <div className="flex items-center gap-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />
          <span>{displayError}</span>
        </div>
      )}
    </div>
  );
}
