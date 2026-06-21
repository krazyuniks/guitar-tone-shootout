/**
 * ToneSearchModal - Modal for searching and selecting tones.
 *
 * Two tabs:
 * - My Gear: Shows gear saved in local library (gear-items API)
 * - Search: Search Tone 3000 catalog for new gear
 *
 * Features:
 * - Search by name/make/model
 * - Filter by gear type (amp, cab, pedal)
 * - Filter by platform (NAM, AIDA-X, IR)
 * - Real-time search results with debounce
 * - Loading and empty states
 */
import { useState, useMemo, useEffect, useCallback } from 'react';
import { Search, X, Loader2, AlertCircle, ChevronDown, Library, Star } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import { api, type Tone, type PaginatedTones, type Gear, type Platform, type GearItemType, type GearItemListResponse } from '@/lib/api';

type ToneSource = 'library' | 'search';

interface ToneSearchModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** Callback when a tone is selected. user_gear_id is provided when selecting from library. */
  onSelect: (tone: Tone, user_gear_id?: string) => void;
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

/** Platform badge colors */
const platformColors: Record<Platform, string> = {
  nam: 'bg-amber-500/20 text-amber-400',
  ir: 'bg-blue-500/20 text-blue-400',
  'aida-x': 'bg-purple-500/20 text-purple-400',
};

/** Gear type colors for library items */
const gearTypeColors: Record<GearItemType, string> = {
  amp: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  full_rig: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  pedal: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  post_effect: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  ir: 'bg-green-500/20 text-green-400 border-green-500/30',
};

/** Library gear type options */
const libraryGearOptions: { value: GearItemType | ''; label: string }[] = [
  { value: '', label: 'All Gear' },
  { value: 'amp', label: 'Amps' },
  { value: 'full_rig', label: 'Full Rigs' },
  { value: 'pedal', label: 'Pedals' },
  { value: 'ir', label: 'IRs' },
  { value: 'post_effect', label: 'Effects' },
];

/** Custom hook for debounced search */
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}

/** Hook to search Tone 3000 catalog */
function useSearchTones(
  enabled: boolean,
  searchQuery: string,
  gear: Gear | '',
  platform: Platform | ''
) {
  const debouncedQuery = useDebounce(searchQuery, 300);

  return useQuery({
    queryKey: ['tones', 'search', debouncedQuery, gear, platform],
    queryFn: () => {
      const params = new URLSearchParams();
      if (debouncedQuery) params.set('query', debouncedQuery);
      if (gear) params.set('gear', gear);
      if (platform) params.set('platform', platform);
      params.set('per_page', '50');
      return api.get<PaginatedTones>(`/tones/search?${params.toString()}`);
    },
    enabled,
  });
}

/** Hook to fetch user's gear library — stub, endpoint not yet implemented */
function useGearLibrary(_enabled: boolean) {
  return useQuery({
    queryKey: ['gear-items'],
    queryFn: () => Promise.resolve({ gear_items: [], total: 0, page: 1, page_size: 100 } as GearItemListResponse),
    staleTime: 30000,
    enabled: false,
  });
}

/**
 * Map a GearItemListItem to a minimal Tone object for display.
 * This avoids an extra API call to T3K when selecting from library.
 */
function gearItemToTone(item: {
  display_name: string | null;
  model_name: string | null;
  pack_title: string | null;
  gear_type: GearItemType;
  tone3000_tone_id: number | null;
  tags: { id: string; name: string; category: string | null }[];
}): Tone {
  // Map gear_type to Gear format (full_rig → full-rig)
  const gearMap: Record<GearItemType, Gear> = {
    amp: 'amp',
    full_rig: 'full-rig',
    pedal: 'pedal',
    ir: 'ir',
    post_effect: 'pedal', // Post-effects are pedals in T3K
  };

  return {
    id: item.tone3000_tone_id?.toString() ?? '0',
    title: item.display_name ?? item.model_name ?? 'Unknown Model',
    description: null,
    gear: gearMap[item.gear_type] ?? 'amp',
    platform: 'nam', // Default platform - gear items are typically NAM
    tags: item.tags.map((t, i) => ({ id: i, name: t.name })),
    makes: item.pack_title ? [{ id: 0, name: item.pack_title }] : [],
    links: [],  // Links not available from gear items
    models_count: 1,
    downloads_count: 0,
    favorites_count: 0,
    license: 'custom',
    creator: null,
    updated_at: null,
  };
}

export function ToneSearchModal({
  isOpen,
  onClose,
  onSelect,
  gearFilter,
  title = 'Select Tone',
}: ToneSearchModalProps) {
  const [source, setSource] = useState<ToneSource>('library');
  const [searchQuery, setSearchQuery] = useState('');
  const [gear, setGear] = useState<Gear | ''>(gearFilter ?? '');
  // Default to NAM platform (UI hidden, but backend support retained for future multi-platform)
  const [platform] = useState<Platform>('nam');

  // Library-specific state
  const [librarySearch, setLibrarySearch] = useState('');
  const [libraryGearFilter, setLibraryGearFilter] = useState<GearItemType | ''>('');

  // Map Gear type to GearItemType for library filtering
  const gearToLibraryGearType = (gear: Gear): GearItemType | '' => {
    const mapping: Record<Gear, GearItemType | ''> = {
      'amp': 'amp',
      'full-rig': 'full_rig',
      'pedal': 'pedal',
      'ir': 'ir',
      'outboard': 'pedal', // Outboard maps to pedal
    };
    return mapping[gear] ?? '';
  };

  // Reset filters when gearFilter prop changes - sync both search and library filters
  useEffect(() => {
    if (gearFilter) {
      setGear(gearFilter);
      // Also set the library filter to match
      setLibraryGearFilter(gearToLibraryGearType(gearFilter));
    }
  }, [gearFilter]);

  // Fetch tones for search tab
  const searchQuery_result = useSearchTones(source === 'search', searchQuery, gear, platform);
  const tones = searchQuery_result.data?.data ?? [];

  // Fetch gear library for library tab
  const gearLibraryQuery = useGearLibrary(source === 'library');

  // Filter library items based on search and gear type
  const filteredLibraryItems = useMemo(() => {
    const items = gearLibraryQuery.data?.gear_items ?? [];
    return items.filter((item) => {
      // Filter by search query
      if (librarySearch) {
        const searchLower = librarySearch.toLowerCase();
        const displayName = (item.display_name ?? item.model_name ?? '').toLowerCase();
        const packTitle = item.pack_title?.toLowerCase() ?? '';
        if (!displayName.includes(searchLower) && !packTitle.includes(searchLower)) return false;
      }
      // Filter by gear type
      if (libraryGearFilter && item.gear_type !== libraryGearFilter) {
        return false;
      }
      return true;
    });
  }, [gearLibraryQuery.data, librarySearch, libraryGearFilter]);

  // Filter tones by gear if a filter is set
  const filteredTones = useMemo(() => {
    if (!gearFilter) return tones;
    return tones.filter((t) => t.gear === gearFilter);
  }, [tones, gearFilter]);

  // Handle tone selection
  const handleSelect = useCallback(
    (tone: Tone, user_gear_id?: string) => {
      onSelect(tone, user_gear_id);
      onClose();
    },
    [onSelect, onClose]
  );

  // Handle gear item click - create Tone from gear item data (no T3K API call)
  // This avoids the slow T3K API call when selecting from user's library
  const handleGearItemClick = useCallback(
    (item: typeof filteredLibraryItems[number]) => {
      const tone = gearItemToTone(item);
      handleSelect(tone, item.id);
    },
    [handleSelect]
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
            {(['library', 'search'] as const).map((s) => (
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
                {s === 'library' ? 'My Gear' : 'Search'}
              </button>
            ))}
          </div>

          {/* Search and filters (for library tab) */}
          {source === 'library' && (
            <div className="flex flex-col gap-3 sm:flex-row">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search saved gear..."
                  value={librarySearch}
                  onChange={(e) => setLibrarySearch(e.target.value)}
                  className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
                  autoFocus
                />
              </div>
              <div className="relative">
                <select
                  value={libraryGearFilter}
                  onChange={(e) => setLibraryGearFilter(e.target.value as GearItemType | '')}
                  className="h-10 appearance-none rounded-md border border-input bg-background pl-3 pr-8 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
                >
                  {libraryGearOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              </div>
            </div>
          )}

          {/* Search input and filters (for search tab) */}
          {source === 'search' && (
            <div className="flex flex-col gap-3 sm:flex-row">
              {/* Search input */}
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search gear..."
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

              </div>
            </div>
          )}
        </div>

        {/* Results - Library tab */}
        {source === 'library' && (
          <div className="flex-1 overflow-y-auto">
            {gearLibraryQuery.isLoading ? (
              <div className="flex h-64 items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : gearLibraryQuery.error ? (
              <div className="flex h-64 flex-col items-center justify-center gap-2 text-muted-foreground">
                <AlertCircle className="h-8 w-8" />
                <p className="text-sm">{gearLibraryQuery.error.message}</p>
              </div>
            ) : filteredLibraryItems.length === 0 ? (
              <div className="flex h-64 flex-col items-center justify-center gap-2 text-muted-foreground">
                <Library className="h-8 w-8" />
                <p className="text-sm">
                  {librarySearch || libraryGearFilter
                    ? 'No matching gear found'
                    : 'No saved gear yet. Save gear from the Search tab!'}
                </p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {filteredLibraryItems.map((item) => {
                  const displayName = item.display_name ?? item.model_name ?? 'Saved model';
                  const subtitle = item.pack_title ?? '';

                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => handleGearItemClick(item)}
                      className="flex w-full items-start gap-4 px-6 py-4 text-left transition-colors hover:bg-muted/50"
                    >
                      {/* Gear type badge */}
                      <span
                        className={cn(
                          'shrink-0 rounded border px-2 py-0.5 text-xs font-medium',
                          gearTypeColors[item.gear_type]
                        )}
                      >
                        {item.gear_type.toUpperCase()}
                      </span>

                      {/* Gear info */}
                      <div className="min-w-0 flex-1">
                        <h4 className="truncate font-medium text-foreground">
                          {displayName}
                        </h4>
                        {subtitle && (
                          <p className="mt-0.5 truncate text-sm text-muted-foreground">
                            {subtitle}
                          </p>
                        )}
                      </div>

                      {/* Status indicator */}
                      <div className="shrink-0">
                        {item.is_favorite && (
                          <Star className="h-5 w-5 fill-amber-500 text-amber-500" />
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Results - Search tab */}
        {source === 'search' && (
          <div className="flex-1 overflow-y-auto">
            {searchQuery_result.isLoading ? (
              <div className="flex h-64 items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : searchQuery_result.error ? (
              <div className="flex h-64 flex-col items-center justify-center gap-2 text-muted-foreground">
                <AlertCircle className="h-8 w-8" />
                <p className="text-sm">{searchQuery_result.error.message}</p>
              </div>
            ) : filteredTones.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-muted-foreground">
                <p className="text-sm">No gear found</p>
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
        )}

        {/* Footer */}
        <div className="border-t border-border px-6 py-3">
          <p className="text-sm text-muted-foreground">
            {source === 'library'
              ? `${filteredLibraryItems.length} gear item${filteredLibraryItems.length !== 1 ? 's' : ''} in library`
              : `${filteredTones.length} gear item${filteredTones.length !== 1 ? 's' : ''} available`}
          </p>
        </div>
      </div>
    </div>
  );
}
