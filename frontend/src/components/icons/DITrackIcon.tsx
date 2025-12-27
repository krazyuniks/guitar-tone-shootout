import * as React from "react";
import { cn } from "@/lib/utils";

interface DITrackIconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
}

/**
 * DI Track Icon - Audio waveform visual
 * Color: Blue #3b82f6 (--color-block-di)
 * Represents DI/input audio tracks in the signal chain
 */
export function DITrackIcon({ className, ...props }: DITrackIconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("h-5 w-5", className)}
      {...props}
    >
      {/* Audio waveform bars */}
      <line x1="4" y1="8" x2="4" y2="16" />
      <line x1="7" y1="5" x2="7" y2="19" />
      <line x1="10" y1="9" x2="10" y2="15" />
      <line x1="13" y1="3" x2="13" y2="21" />
      <line x1="16" y1="7" x2="16" y2="17" />
      <line x1="19" y1="10" x2="19" y2="14" />
    </svg>
  );
}
