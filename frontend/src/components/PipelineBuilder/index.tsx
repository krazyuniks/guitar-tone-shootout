/**
 * PipelineBuilder - Main component for creating tone comparisons.
 *
 * Allows users to:
 * - Select 2-4 tones from Tone 3000
 * - Upload a DI track
 * - Add a title and description
 * - Submit for processing
 */
import type React from 'react';
import { useState, useCallback } from 'react';
import { Loader2, AlertCircle, Zap, LogIn } from 'lucide-react';
import { QueryProvider } from '@/lib/query';
import { ToneSelector } from './ToneSelector';
import { ToneCard } from './ToneCard';
import { DITrackUpload } from './DITrackUpload';
import { useJobSubmit, useFileUpload, useAuth } from './hooks';
import type { Tone } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ComparisonForm {
  title: string;
  description: string;
}

function PipelineBuilderInner() {
  const [selectedTones, setSelectedTones] = useState<Tone[]>([]);
  const [diFile, setDiFile] = useState<File | null>(null);
  const [uploadedPath, setUploadedPath] = useState<string | null>(null);
  const [form, setForm] = useState<ComparisonForm>({ title: '', description: '' });
  const [submitError, setSubmitError] = useState<string | null>(null);

  const auth = useAuth();
  const fileUpload = useFileUpload();
  const jobSubmit = useJobSubmit();

  // Show loading state while checking auth
  if (auth.isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-amber-500" />
      </div>
    );
  }

  // Show login prompt if not authenticated
  if (!auth.data?.authenticated) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center gap-6 rounded-lg border border-border bg-card p-8 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-amber-500/20">
          <LogIn className="h-8 w-8 text-amber-500" />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-semibold">Sign in to Continue</h2>
          <p className="text-muted-foreground">
            Connect your Tone 3000 account to access your tones and create comparisons.
          </p>
        </div>
        <Button
          asChild
          size="lg"
          className="bg-amber-500 hover:bg-amber-600"
        >
          <a href="/login">
            <LogIn className="mr-2 h-4 w-4" />
            Sign in with Tone 3000
          </a>
        </Button>
      </div>
    );
  }

  const handleToneSelect = useCallback((tone: Tone) => {
    setSelectedTones((prev) => [...prev, tone]);
  }, []);

  const handleToneRemove = useCallback((toneId: number) => {
    setSelectedTones((prev) => prev.filter((t) => t.id !== toneId));
  }, []);

  const handleFileSelect = useCallback(
    async (file: File | null) => {
      setDiFile(file);
      setUploadedPath(null);

      if (file) {
        try {
          const result = await fileUpload.mutateAsync(file);
          setUploadedPath(result.path);
        } catch {
          // Error is handled by mutation state
        }
      }
    },
    [fileUpload]
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    // Validation
    if (selectedTones.length < 2) {
      setSubmitError('Please select at least 2 tones to compare');
      return;
    }

    if (!diFile) {
      setSubmitError('Please upload a DI track');
      return;
    }

    try {
      const job = await jobSubmit.mutateAsync({
        toneIds: selectedTones.map((t) => t.id),
        diTrackPath: uploadedPath ?? undefined,
        title: form.title || undefined,
        description: form.description || undefined,
      });

      // Redirect to job progress page
      window.location.href = `/jobs/${job.id}`;
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to create job');
    }
  };

  const isValid = selectedTones.length >= 2 && diFile !== null;
  const isSubmitting = fileUpload.isPending || jobSubmit.isPending;

  return (
    <form onSubmit={handleSubmit} className="space-y-10">
      {/* Step 1: Select Tones */}
      <section className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-500 text-sm font-bold text-background">
            1
          </div>
          <h2 className="text-xl font-semibold">Select Tones to Compare</h2>
        </div>

        <ToneSelector
          selectedTones={selectedTones}
          onSelect={handleToneSelect}
          maxSelections={4}
        />

        {/* Selected tones grid */}
        {selectedTones.length > 0 && (
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {selectedTones.map((tone) => (
              <ToneCard
                key={tone.id}
                tone={tone}
                onRemove={() => handleToneRemove(tone.id)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Step 2: Upload DI Track */}
      <section className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-500 text-sm font-bold text-background">
            2
          </div>
          <h2 className="text-xl font-semibold">Upload DI Track</h2>
        </div>

        <p className="text-sm text-muted-foreground">
          Upload the dry/direct guitar recording that will be processed through each tone.
        </p>

        <DITrackUpload
          file={diFile}
          onFileSelect={handleFileSelect}
          isUploading={fileUpload.isPending}
          error={fileUpload.error?.message}
        />
      </section>

      {/* Step 3: Comparison Details (Optional) */}
      <section className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-sm font-bold text-muted-foreground">
            3
          </div>
          <h2 className="text-xl font-semibold text-muted-foreground">
            Comparison Details{' '}
            <span className="text-sm font-normal">(Optional)</span>
          </h2>
        </div>

        <div className="space-y-4 rounded-lg border border-border bg-card p-4">
          <div>
            <label
              htmlFor="title"
              className="block text-sm font-medium text-foreground"
            >
              Title
            </label>
            <input
              type="text"
              id="title"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="e.g., Clean vs Crunch Comparison"
              className="mt-1 h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
          </div>

          <div>
            <label
              htmlFor="description"
              className="block text-sm font-medium text-foreground"
            >
              Description
            </label>
            <textarea
              id="description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="Add notes about this comparison..."
              rows={3}
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
          </div>
        </div>
      </section>

      {/* Error message */}
      {(submitError || jobSubmit.error) && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <p className="text-sm">{submitError || jobSubmit.error?.message}</p>
        </div>
      )}

      {/* Submit button */}
      <div className="flex flex-col items-center gap-4 pt-4">
        <Button
          type="submit"
          size="lg"
          disabled={!isValid || isSubmitting}
          className={cn(
            'h-12 w-full max-w-md gap-2 text-base',
            isValid && !isSubmitting && 'bg-amber-500 hover:bg-amber-600'
          )}
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              Creating Comparison...
            </>
          ) : (
            <>
              <Zap className="h-5 w-5" />
              Create Comparison
            </>
          )}
        </Button>

        {!isValid && (
          <p className="text-sm text-muted-foreground">
            {selectedTones.length < 2
              ? `Select ${2 - selectedTones.length} more tone${2 - selectedTones.length > 1 ? 's' : ''} to continue`
              : 'Upload a DI track to continue'}
          </p>
        )}
      </div>
    </form>
  );
}

/**
 * PipelineBuilder wrapped with QueryProvider for data fetching.
 */
export default function PipelineBuilder() {
  return (
    <QueryProvider>
      <PipelineBuilderInner />
    </QueryProvider>
  );
}
