/**
 * SectionRow - A horizontal scrollable row of shootout cards with a section header.
 * Used on the browse page to display categorized shootouts.
 */

import type { ReactNode } from 'react';
import type { ShootoutListItem } from '@/lib/api';
import { ShootoutCard } from './ShootoutCard';
import { cn } from '@/lib/utils';

interface SectionRowProps {
  title: string;
  icon?: ReactNode;
  shootouts: ShootoutListItem[];
  viewAllHref?: string;
  className?: string;
  isLoading?: boolean;
  emptyMessage?: string;
}

function LoadingCard() {
  return (
    <div className="min-w-[280px] max-w-[320px] flex-shrink-0 rounded-lg overflow-hidden bg-[var(--color-bg-surface)] border border-[var(--border)]">
      <div className="aspect-video bg-[var(--color-bg-elevated)] animate-pulse" />
      <div className="p-4 space-y-3">
        <div className="h-5 bg-[var(--color-bg-elevated)] rounded animate-pulse" />
        <div className="h-4 bg-[var(--color-bg-elevated)] rounded w-2/3 animate-pulse" />
        <div className="h-3 bg-[var(--color-bg-elevated)] rounded w-1/3 animate-pulse" />
      </div>
    </div>
  );
}

export function SectionRow({
  title,
  icon,
  shootouts,
  viewAllHref,
  className,
  isLoading = false,
  emptyMessage = 'No shootouts yet',
}: SectionRowProps) {
  return (
    <section className={cn('py-6', className)}>
      {/* Section header */}
      <div className="flex items-center justify-between mb-4 px-4 md:px-0">
        <h2 className="text-xl font-bold text-[var(--color-text-primary)] flex items-center gap-2">
          {icon}
          {title}
        </h2>
        {viewAllHref && shootouts.length > 0 && (
          <a
            href={viewAllHref}
            className="text-sm font-medium text-amber-500 hover:text-amber-400 transition-colors flex items-center gap-1"
          >
            View All
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-4 h-4"
            >
              <path
                fillRule="evenodd"
                d="M3 10a.75.75 0 01.75-.75h10.638L10.23 5.29a.75.75 0 111.04-1.08l5.5 5.25a.75.75 0 010 1.08l-5.5 5.25a.75.75 0 11-1.04-1.08l4.158-3.96H3.75A.75.75 0 013 10z"
                clipRule="evenodd"
              />
            </svg>
          </a>
        )}
      </div>

      {/* Horizontal scroll container */}
      <div className="relative">
        <div className="flex gap-4 overflow-x-auto pb-4 px-4 md:px-0 scrollbar-thin scrollbar-thumb-[var(--color-bg-elevated)] scrollbar-track-transparent">
          {isLoading ? (
            // Loading state
            <>
              <LoadingCard />
              <LoadingCard />
              <LoadingCard />
              <LoadingCard />
            </>
          ) : shootouts.length === 0 ? (
            // Empty state
            <div className="min-w-full flex items-center justify-center py-12 text-[var(--color-text-muted)]">
              <div className="text-center">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  className="w-12 h-12 mx-auto mb-3 opacity-50"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M2.25 13.5h3.86a2.25 2.25 0 012.012 1.244l.256.512a2.25 2.25 0 002.013 1.244h3.218a2.25 2.25 0 002.013-1.244l.256-.512a2.25 2.25 0 012.013-1.244h3.859m-19.5.338V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18v-4.162c0-.224-.034-.447-.1-.661L19.24 5.338a2.25 2.25 0 00-2.15-1.588H6.911a2.25 2.25 0 00-2.15 1.588L2.35 13.177a2.25 2.25 0 00-.1.661z"
                  />
                </svg>
                <p>{emptyMessage}</p>
              </div>
            </div>
          ) : (
            // Shootout cards
            shootouts.map((shootout) => (
              <ShootoutCard
                key={shootout.id}
                shootout={shootout}
                className="min-w-[280px] max-w-[320px] flex-shrink-0"
              />
            ))
          )}
        </div>

        {/* Fade edges for scroll indication */}
        {shootouts.length > 3 && !isLoading && (
          <>
            <div className="absolute left-0 top-0 bottom-4 w-8 bg-gradient-to-r from-[var(--color-bg-base)] to-transparent pointer-events-none md:hidden" />
            <div className="absolute right-0 top-0 bottom-4 w-8 bg-gradient-to-l from-[var(--color-bg-base)] to-transparent pointer-events-none" />
          </>
        )}
      </div>
    </section>
  );
}

export default SectionRow;
