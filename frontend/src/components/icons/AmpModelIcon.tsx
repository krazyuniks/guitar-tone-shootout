import * as React from "react";
import { cn } from "@/lib/utils";

interface AmpModelIconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
}

/**
 * Amp Model Icon - Amplifier stack visual
 * Color: Amber #f59e0b (--color-block-amp)
 * Represents NAM/amp model blocks in the signal chain
 */
export function AmpModelIcon({ className, ...props }: AmpModelIconProps) {
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
      {/* Amp cabinet body */}
      <rect x="3" y="3" width="18" height="18" rx="2" />
      {/* Speaker grille circle */}
      <circle cx="12" cy="13" r="5" />
      {/* Control knobs */}
      <circle cx="7" cy="6" r="1" fill="currentColor" />
      <circle cx="12" cy="6" r="1" fill="currentColor" />
      <circle cx="17" cy="6" r="1" fill="currentColor" />
      {/* Speaker cone detail */}
      <circle cx="12" cy="13" r="2" />
    </svg>
  );
}
