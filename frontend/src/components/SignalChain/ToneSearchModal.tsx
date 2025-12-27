/**
 * ToneSearchModal - Modal for searching and selecting tones from Tone 3000.
 *
 * Features:
 * - Search by name/make/model
 * - Filter by gear type (amp, cab, pedal)
 * - Filter by platform (NAM, AIDA-X, IR)
 * - Browse user's library and favorites
 * - Real-time search results with debounce
 * - Loading and empty states
 */
import { useState, useMemo, useEffect, useCallback } from 'react';
import { Search, X, Loader2, AlertCircle, ChevronDown } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import { api, type Tone, type PaginatedTones, type Gear, type Platform } from '@/lib/api';

type ToneSource = 'mine' | 'favorites' | 'search';

interface ToneSearchModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** Callback when a tone is selected */
  onSelect: (tone: Tone) => void;
  /** Filter to specific gear types */
  gearFilter?: Gear;
  /** Modal title */
  title?: string;
}

/** Gear type options */
const gearOptions: { value: Gear | ''; label: string }[] = [
  { value: '', label: 'All Types' },
  { value: 'amp', label: 'Amps' },
  { value: 'full-rig', label: 'Full Rigs' },
  { value: 'pedal', label: 'Pedals' },
  { value: 'outboard', label: 'Outboard' },
  { value: 'ir', label: 'IRs/Cabs' },
];

/** Platform options */
const platformOptions: { value: Platform | ''; label: string }[] = [
  { value: '', label: 'All Platforms' },
  { value: 'nam', label: 'NAM' },
  { value: 'ir', label: 'IR' },
  { value: 'aida-x', label: 'AIDA-X' },
];

/** Platform badge colors */
const platformColors: Record<Platform, string> = {
  nam: 'bg-amber-500/20 text-amber-400',
  ir: 'bg-blue-500/20 text-blue-400',
  'aida-x': 'bg-purple-500/20 text-purple-400',
};

/** Custom hook for debounced search */
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}

/** Hook to fetch tones based on source and filters */
function useTones(
  source: ToneSource,
  searchQuery: string,
  gear: Gear | '',
  platform: Platform | ''
) {
  const debouncedQuery = useDebounce(searchQuery, 300);

  const myTones = useQuery({
    queryKey: ['tones', 'mine'],
    queryFn: () => api.get<PaginatedTones>('/tones/mine?per_page=50'),
    enabled: source === 'mine',
  });

  const favorites = useQuery({
    queryKey: ['tones', 'favorites'],
    queryFn: () => api.get<PaginatedTones>('/tones/favorites?per_page=50'),
    enabled: source === 'favorites',
  });

  const search = useQuery({
    queryKey: ['tones', 'search', debouncedQuery, gear, platform],
    queryFn: () => {
      const params = new URLSearchParams();
      if (debouncedQuery) params.set('query', debouncedQuery);
      if (gear) params.set('gear', gear);
      if (platform) params.set('platform', platform);
      params.set('per_page', '50');
      return api.get<PaginatedTones>(`/tones/search?${params.toString()}`);
    },
    enabled: source === 'search',
  });

  return source === 'mine' ? myTones : source === 'favorites' ? favorites : search;
}

export function ToneSearchModal({
  isOpen,
  onClose,
  onSelect,
  gearFilter,
  title = 'Select Tone',
}: ToneSearchModalProps) {
  const [source, setSource] = useState<ToneSource>('mine');
  const [searchQuery, setSearchQuery] = useState('');
  const [gear, setGear] = useState<Gear | ''>(gearFilter ?? '');
  const [platform, setPlatform] = useState<Platform | ''>('');

  // Reset filters when gearFilter prop changes
  useEffect(() => {
    if (gearFilter) {
      setGear(gearFilter);
    }
  }, [gearFilter]);

  // Fetch tones
  const { data, isLoading, error } = useTones(source, searchQuery, gear, platform);
  const tones = data?.data ?? [];

  // Filter tones by gear if a filter is set
  const filteredTones = useMemo(() => {
    if (!gearFilter) return tones;
    return tones.filter((t) => t.gear === gearFilter);
  }, [tones, gearFilter]);

  // Handle tone selection
  const handleSelect = useCallback(
    (tone: Tone) => {
      onSelect(tone);
      onClose();
    },
    [onSelect, onClose]
  );

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div className="relative z-10 flex max-h-[90vh] w-full max-w-2xl flex-col rounded-lg border border-border bg-card shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="text-lg font-semibold text-foreground">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="Close modal"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Search and filters */}
        <div className="border-b border-border px-6 py-4">
          {/* Source tabs */}
          <div className="mb-4 flex gap-2 border-b border-border">
            {(['mine', 'favorites', 'search'] as const).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setSource(s)}
                className={cn(
                  'border-b-2 px-4 py-2 text-sm font-medium transition-colors',
                  source === s
                    ? 'border-amber-500 text-amber-500'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                )}
              >
                {s === 'mine' ? 'My Tones' : s === 'favorites' ? 'Favorites' : 'Search'}
              </button>
            ))}
          </div>

          {/* Search input and filters (for search tab) */}
          {source === 'search' && (
            <div className="flex flex-col gap-3 sm:flex-row">
              {/* Search input */}
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search tones..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
                  autoFocus
                />
              </div>

              {/* Filters */}
              <div className="flex gap-2">
                {/* Gear filter (only if not locked by prop) */}
                {!gearFilter && (
                  <div className="relative">
                    <select
                      value={gear}
                      onChange={(e) => setGear(e.target.value as Gear | '')}
                      className="h-10 appearance-none rounded-md border border-input bg-background pl-3 pr-8 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
                    >
                      {gearOptions.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  </div>
                )}

                {/* Platform filter */}
                <div className="relative">
                  <select
                    value={platform}
                    onChange={(e) => setPlatform(e.target.value as Platform | '')}
                    className="h-10 appearance-none rounded-md border border-input bg-background pl-3 pr-8 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
                  >
                    {platformOptions.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="flex h-64 flex-col items-center justify-center gap-2 text-muted-foreground">
              <AlertCircle className="h-8 w-8" />
              <p className="text-sm">{error.message}</p>
            </div>
          ) : filteredTones.length === 0 ? (
            <div className="flex h-64 items-center justify-center text-muted-foreground">
              <p className="text-sm">
                {source === 'mine'
                  ? 'You have no tones yet'
                  : source === 'favorites'
                    ? 'No favorites yet'
                    : 'No tones found'}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {filteredTones.map((tone) => (
                <button
                  key={tone.id}
                  type="button"
                  onClick={() => handleSelect(tone)}
                  className="flex w-full items-start gap-4 px-6 py-4 text-left transition-colors hover:bg-muted/50"
                >
                  {/* Tone info */}
                  <div className="min-w-0 flex-1">
                    <h4 className="truncate font-medium text-foreground">
                      {tone.title}
                    </h4>
                    <p className="mt-0.5 text-sm text-muted-foreground">
                      {tone.makes.length > 0 && `${tone.makes[0].name} · `}
                      {tone.gear.replace('-', ' ')}
                    </p>
                    {/* Tags */}
                    {tone.tags.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {tone.tags.slice(0, 3).map((tag) => (
                          <span
                            key={tag.id}
                            className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
                          >
                            {tag.name}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Platform badge */}
                  <span
                    className={cn(
                      'shrink-0 rounded-full px-2 py-0.5 text-xs font-medium',
                      platformColors[tone.platform]
                    )}
                  >
                    {tone.platform.toUpperCase()}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-border px-6 py-3">
          <p className="text-sm text-muted-foreground">
            {filteredTones.length} tone{filteredTones.length !== 1 ? 's' : ''} available
          </p>
        </div>
      </div>
    </div>
  );
}
