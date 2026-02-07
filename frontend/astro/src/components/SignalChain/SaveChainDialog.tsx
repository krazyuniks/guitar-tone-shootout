/**
 * SaveChainDialog - Dialog for saving a signal chain.
 *
 * Prompts user for name and platform, then saves to the API.
 *
 * V2 Schema: Uses user_gear_id to reference UserGear items from user's library.
 */
import { useState, useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Save, X, Loader2, Link2 } from 'lucide-react';
import {
  signalChainApi,
  type SignalChainCreate,
  type SignalChainBlockCreate,
  type SignalChainPlatform,
} from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { BuilderState } from './types';
import { getErrorMessage } from '@/lib/error-handling';

interface SaveChainDialogProps {
  /** Whether the dialog is open */
  isOpen: boolean;
  /** Close handler */
  onClose: () => void;
  /** Current builder state to save */
  builderState: BuilderState;
  /** Success callback with the new chain ID */
  onSuccess?: (chainId: string) => void;
}

/**
 * Convert builder state to API format (V2 schema with user_gear_id).
 *
 * Returns blocks that have user_gear_id set. Blocks without user_gear_id
 * are skipped (they were added from T3K search, not user's library).
 */
function stateToApiBlocks(state: BuilderState): SignalChainBlockCreate[] {
  const blocks: SignalChainBlockCreate[] = [];
  let position = 0;

  // Effects (pedals) go first in signal chain
  for (const effect of state.effects) {
    if (effect.user_gear_id) {
      blocks.push({
        position: position++,
        user_gear_id: effect.user_gear_id,
      });
    }
  }

  // Amps
  for (const amp of state.amps) {
    if (amp.user_gear_id) {
      blocks.push({
        position: position++,
        user_gear_id: amp.user_gear_id,
      });
    }
  }

  // Cabinets (IRs)
  for (const cab of state.cabs) {
    if (cab.user_gear_id) {
      blocks.push({
        position: position++,
        user_gear_id: cab.user_gear_id,
      });
    }
  }

  return blocks;
}

export function SaveChainDialog({
  isOpen,
  onClose,
  builderState,
  onSuccess,
}: SaveChainDialogProps) {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [platform, setPlatform] = useState<SignalChainPlatform>('nam');
  const [error, setError] = useState<string | null>(null);

  // Count blocks for summary
  const blockCount =
    builderState.amps.length +
    builderState.cabs.length +
    builderState.effects.length;

  const hasBlocks = blockCount > 0;

  // Check if all blocks can be saved (have user_gear_id)
  const savableBlockCount = stateToApiBlocks(builderState).length;

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: async (data: SignalChainCreate) => {
      return signalChainApi.create(data);
    },
    onSuccess: (chain) => {
      queryClient.invalidateQueries({ queryKey: ['signal-chains'] });
      onSuccess?.(chain.id);
      handleClose();
    },
    onError: (err) => {
      setError(getErrorMessage(err));
    },
  });

  const handleClose = useCallback(() => {
    setName('');
    setPlatform('nam');
    setError(null);
    onClose();
  }, [onClose]);

  const handleSave = useCallback(() => {
    if (!name.trim()) {
      setError('Please enter a name');
      return;
    }

    if (!hasBlocks) {
      setError('Add at least one block to save');
      return;
    }

    if (savableBlockCount === 0) {
      setError('All blocks must be from your Gear Library. Add gear to your library first.');
      return;
    }

    setError(null);

    const blocks = stateToApiBlocks(builderState);

    saveMutation.mutate({
      name: name.trim(),
      platform,
      blocks,
    });
  }, [name, platform, hasBlocks, savableBlockCount, builderState, saveMutation]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Dialog */}
      <div className="relative z-10 w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-xl">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--color-accent-primary)]/20">
              <Link2 className="h-5 w-5 text-[var(--color-accent-primary)]" />
            </div>
            <h2 className="text-xl font-semibold text-foreground">
              Save Signal Chain
            </h2>
          </div>
          <button
            onClick={handleClose}
            className="rounded-full p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <div className="space-y-4">
          {/* Name input */}
          <div>
            <label
              htmlFor="chain-name"
              className="mb-1.5 block text-sm font-medium text-foreground"
            >
              Chain Name
            </label>
            <Input
              id="chain-name"
              type="text"
              placeholder="e.g., My Blues Rig"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
          </div>

          {/* Platform select */}
          <div>
            <label
              htmlFor="platform"
              className="mb-1.5 block text-sm font-medium text-foreground"
            >
              Platform
            </label>
            <select
              id="platform"
              value={platform}
              onChange={(e) => setPlatform(e.target.value as SignalChainPlatform)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
            >
              <option value="nam">NAM (Neural Amp Modeler)</option>
              <option value="aida_x">AIDA-X</option>
            </select>
          </div>

          {/* Summary */}
          <div className="rounded-lg bg-muted/50 p-4">
            <h3 className="mb-2 text-sm font-medium text-foreground">
              Chain Summary
            </h3>
            <ul className="space-y-1 text-sm text-muted-foreground">
              {builderState.effects.length > 0 && (
                <li>
                  {builderState.effects.length} effect
                  {builderState.effects.length !== 1 ? 's' : ''}
                </li>
              )}
              {builderState.amps.length > 0 && (
                <li>
                  {builderState.amps.length} amp
                  {builderState.amps.length !== 1 ? 's' : ''}
                </li>
              )}
              {builderState.cabs.length > 0 && (
                <li>
                  {builderState.cabs.length} cabinet
                  {builderState.cabs.length !== 1 ? 's' : ''} / IR
                  {builderState.cabs.length !== 1 ? 's' : ''}
                </li>
              )}
              {blockCount === 0 && (
                <li className="text-amber-500">No blocks to save</li>
              )}
            </ul>
          </div>

          {/* Error message */}
          {error && (
            <div className="rounded-lg bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={saveMutation.isPending || !hasBlocks}
          >
            {saveMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" />
                Save Chain
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
