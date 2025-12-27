/**
 * BrowseContent - Main content component for the browse page.
 * Fetches shootouts from the API and displays them in categorized sections.
 */

import { useQuery } from '@tanstack/react-query';
import { api, type ShootoutListResponse } from '@/lib/api';
import { QueryProvider } from '@/lib/query';
import { SectionRow } from './SectionRow';

// Icons for section headers
const TrendingIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
    className="w-5 h-5 text-orange-500"
  >
    <path
      fillRule="evenodd"
      d="M12.963 2.286a.75.75 0 00-1.071-.136 9.742 9.742 0 00-3.539 6.177A7.547 7.547 0 016.648 6.61a.75.75 0 00-1.152.082A9 9 0 1015.68 4.534a7.46 7.46 0 01-2.717-2.248zM15.75 14.25a3.75 3.75 0 11-7.313-1.172c.628.465 1.35.81 2.133 1a5.99 5.99 0 011.925-3.545 3.75 3.75 0 013.255 3.717z"
      clipRule="evenodd"
    />
  </svg>
);

const LatestIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
    className="w-5 h-5 text-yellow-500"
  >
    <path
      fillRule="evenodd"
      d="M14.615 1.595a.75.75 0 01.359.852L12.982 9.75h7.268a.75.75 0 01.548 1.262l-10.5 11.25a.75.75 0 01-1.272-.71l1.992-7.302H3.75a.75.75 0 01-.548-1.262l10.5-11.25a.75.75 0 01.913-.143z"
      clipRule="evenodd"
    />
  </svg>
);

const HighGainIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
    className="w-5 h-5 text-red-500"
  >
    <path d="M19.952 1.651a.75.75 0 01.298.599V16.303a3 3 0 01-2.176 2.884l-1.32.377a2.553 2.553 0 11-1.403-4.909l2.311-.66a1.5 1.5 0 001.088-1.442V6.994l-9 2.572v9.737a3 3 0 01-2.176 2.884l-1.32.377a2.553 2.553 0 11-1.402-4.909l2.31-.66a1.5 1.5 0 001.088-1.442V5.25a.75.75 0 01.544-.721l10.5-3a.75.75 0 01.658.122z" />
  </svg>
);

const CleanIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="currentColor"
    className="w-5 h-5 text-blue-500"
  >
    <path d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zm0 8.625a1.125 1.125 0 100 2.25 1.125 1.125 0 000-2.25zM15.375 12a1.125 1.125 0 112.25 0 1.125 1.125 0 01-2.25 0zM7.5 10.875a1.125 1.125 0 100 2.25 1.125 1.125 0 000-2.25z" />
  </svg>
);

interface BrowseContentInnerProps {
  initialData?: ShootoutListResponse;
}

function BrowseContentInner({ initialData }: BrowseContentInnerProps) {
  // Fetch all public shootouts
  const { data, isLoading, error } = useQuery({
    queryKey: ['shootouts', 'public'],
    queryFn: () => api.get<ShootoutListResponse>('/shootouts/public?page_size=50'),
    initialData,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  // In a real implementation, we'd have different API endpoints for different categories
  // For now, we'll simulate categories by sorting/filtering the same data differently
  const allShootouts = data?.shootouts ?? [];

  // Latest uploads (sorted by creation date, most recent first)
  const latestShootouts = [...allShootouts]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 8);

  // For demo purposes, we'll create mock categories
  // In production, these would come from different API endpoints or have proper filtering
  const trendingShootouts = [...allShootouts]
    .filter((s) => s.is_processed)
    .slice(0, 8);

  // Filter by name patterns for category simulation
  const highGainShootouts = allShootouts
    .filter((s) =>
      s.name.toLowerCase().includes('high') ||
      s.name.toLowerCase().includes('gain') ||
      s.name.toLowerCase().includes('metal') ||
      s.name.toLowerCase().includes('mesa') ||
      s.name.toLowerCase().includes('5150') ||
      s.name.toLowerCase().includes('rectifier')
    )
    .slice(0, 8);

  const cleanShootouts = allShootouts
    .filter((s) =>
      s.name.toLowerCase().includes('clean') ||
      s.name.toLowerCase().includes('fender') ||
      s.name.toLowerCase().includes('twin') ||
      s.name.toLowerCase().includes('jazz') ||
      s.name.toLowerCase().includes('deluxe')
    )
    .slice(0, 8);

  if (error) {
    return (
      <div className="container mx-auto px-4 py-12">
        <div className="text-center">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="w-16 h-16 mx-auto mb-4 text-red-500"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
            />
          </svg>
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-2">
            Failed to load shootouts
          </h2>
          <p className="text-[var(--color-text-secondary)]">
            Please try refreshing the page.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto">
      {/* Hero section */}
      <div className="text-center py-12 px-4">
        <h1 className="text-3xl md:text-4xl font-bold text-[var(--color-text-primary)] mb-4">
          Browse Tone Shootouts
        </h1>
        <p className="text-lg text-[var(--color-text-secondary)] max-w-2xl mx-auto">
          Discover and compare guitar tones from the community. Find your perfect sound.
        </p>
      </div>

      {/* Sections */}
      <div className="space-y-2 pb-12">
        <SectionRow
          title="Trending This Week"
          icon={<TrendingIcon />}
          shootouts={trendingShootouts}
          isLoading={isLoading}
          viewAllHref="/browse/trending"
          emptyMessage="No trending shootouts this week"
        />

        <SectionRow
          title="Latest Uploads"
          icon={<LatestIcon />}
          shootouts={latestShootouts}
          isLoading={isLoading}
          viewAllHref="/browse/latest"
          emptyMessage="No shootouts uploaded yet"
        />

        {highGainShootouts.length > 0 && (
          <SectionRow
            title="High Gain Battle"
            icon={<HighGainIcon />}
            shootouts={highGainShootouts}
            isLoading={isLoading}
            viewAllHref="/browse/high-gain"
            emptyMessage="No high gain shootouts yet"
          />
        )}

        {cleanShootouts.length > 0 && (
          <SectionRow
            title="Clean & Crisp"
            icon={<CleanIcon />}
            shootouts={cleanShootouts}
            isLoading={isLoading}
            viewAllHref="/browse/clean"
            emptyMessage="No clean tone shootouts yet"
          />
        )}

        {/* Show all if no specialized sections */}
        {allShootouts.length > 0 &&
          highGainShootouts.length === 0 &&
          cleanShootouts.length === 0 && (
            <SectionRow
              title="All Shootouts"
              shootouts={allShootouts.slice(0, 12)}
              isLoading={isLoading}
              viewAllHref="/browse/all"
            />
          )}
      </div>
    </div>
  );
}

// Wrapper with QueryProvider for standalone use
interface BrowseContentProps {
  initialData?: ShootoutListResponse;
}

export function BrowseContent({ initialData }: BrowseContentProps) {
  return (
    <QueryProvider>
      <BrowseContentInner initialData={initialData} />
    </QueryProvider>
  );
}

export default BrowseContent;
