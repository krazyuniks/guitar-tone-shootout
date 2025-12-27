import * as React from "react";
import { cn } from "@/lib/utils";
import { Eye, Heart, Play, Video } from "lucide-react";

/**
 * ShootoutCard - React component for displaying shootout previews
 *
 * Used in React contexts for interactive lists with data fetching.
 * For static pages, use ShootoutCard.astro instead.
 */
export interface ShootoutCardProps {
  /** Unique identifier for the shootout */
  id: number;
  /** Shootout title */
  title: string;
  /** URL to thumbnail image */
  thumbnailUrl?: string;
  /** Creator username */
  creator: string;
  /** Creator's avatar URL */
  creatorAvatarUrl?: string;
  /** Genre/category badge text */
  genre?: string;
  /** Duration in seconds */
  duration?: number;
  /** Number of views */
  viewCount?: number;
  /** Number of likes */
  likeCount?: number;
  /** Link to shootout detail page */
  href?: string;
  /** Click handler for the card */
  onClick?: (id: number) => void;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Format duration as MM:SS
 */
function formatDuration(seconds?: number): string {
  if (!seconds) return "";
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

/**
 * Format view count with K/M suffix
 */
function formatViewCount(count: number): string {
  if (count >= 1_000_000) {
    return `${(count / 1_000_000).toFixed(1)}M`;
  }
  if (count >= 1_000) {
    return `${(count / 1_000).toFixed(1)}K`;
  }
  return count.toString();
}

export function ShootoutCard({
  id,
  title,
  thumbnailUrl,
  creator,
  creatorAvatarUrl,
  genre,
  duration,
  viewCount = 0,
  likeCount = 0,
  href,
  onClick,
  className,
}: ShootoutCardProps) {
  const linkHref = href || `/shootouts/${id}`;
  const durationText = formatDuration(duration);

  const handleClick = (e: React.MouseEvent) => {
    if (onClick) {
      e.preventDefault();
      onClick(id);
    }
  };

  const CardWrapper = onClick ? "button" : "a";
  const wrapperProps = onClick
    ? { type: "button" as const, onClick: handleClick }
    : { href: linkHref };

  return (
    <article
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-lg border border-border bg-card transition-all duration-200 hover:scale-[1.02] hover:border-amber-500/50 hover:shadow-lg hover:shadow-amber-500/5",
        className
      )}
    >
      {/* Thumbnail */}
      <CardWrapper
        {...wrapperProps}
        className="relative aspect-video overflow-hidden bg-[var(--color-bg-elevated)]"
      >
        {thumbnailUrl ? (
          <img
            src={thumbnailUrl}
            alt={`Thumbnail for ${title}`}
            className="h-full w-full object-cover transition-transform duration-200 group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <Video className="h-12 w-12 text-muted-foreground" />
          </div>
        )}

        {/* Play button overlay (visible on hover) */}
        <div className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-amber-500 text-white shadow-lg">
            <Play className="h-6 w-6 translate-x-0.5 fill-current" />
          </div>
        </div>

        {/* Badge overlays */}
        <div className="absolute bottom-2 left-2 right-2 flex items-end justify-between">
          {genre && (
            <span className="rounded bg-black/70 px-2 py-0.5 text-xs font-medium text-white backdrop-blur-sm">
              {genre}
            </span>
          )}
          {durationText && (
            <span className="rounded bg-black/70 px-2 py-0.5 text-xs font-medium tabular-nums text-white backdrop-blur-sm">
              {durationText}
            </span>
          )}
        </div>
      </CardWrapper>

      {/* Content */}
      <div className="flex flex-1 flex-col gap-2 p-4">
        {/* Title */}
        <a
          href={linkHref}
          className="line-clamp-2 font-medium leading-snug text-foreground hover:text-amber-500"
          onClick={onClick ? handleClick : undefined}
        >
          {title}
        </a>

        {/* Creator info */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          {creatorAvatarUrl ? (
            <img
              src={creatorAvatarUrl}
              alt={creator}
              className="h-5 w-5 rounded-full object-cover"
              loading="lazy"
            />
          ) : (
            <div className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--color-bg-elevated)] text-xs uppercase">
              {creator.charAt(0)}
            </div>
          )}
          <span className="truncate">{creator}</span>
        </div>

        {/* Stats */}
        <div className="mt-auto flex items-center gap-4 pt-2 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Eye className="h-3.5 w-3.5" />
            <span className="tabular-nums">{formatViewCount(viewCount)}</span>
          </span>
          <span className="flex items-center gap-1">
            <Heart className="h-3.5 w-3.5" />
            <span className="tabular-nums">{formatViewCount(likeCount)}</span>
          </span>
        </div>
      </div>
    </article>
  );
}
