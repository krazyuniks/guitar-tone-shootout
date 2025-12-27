import * as React from "react";
import { cn } from "@/lib/utils";

interface EffectIconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
}

/**
 * Effect Icon - Guitar pedal/knob visual
 * Color: Purple #a855f7 (--color-block-effect)
 * Represents effects/pedals in the signal chain
 */
export function EffectIcon({ className, ...props }: EffectIconProps) {
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
      {/* Pedal body */}
      <rect x="4" y="4" width="16" height="16" rx="2" />
      {/* Main control knob */}
      <circle cx="12" cy="10" r="3" />
      {/* Knob indicator */}
      <line x1="12" y1="10" x2="12" y2="8" />
      {/* Footswitch */}
      <rect x="8" y="15" width="8" height="3" rx="1" />
      {/* Input/output jacks */}
      <circle cx="6" cy="12" r="1" fill="currentColor" />
      <circle cx="18" cy="12" r="1" fill="currentColor" />
    </svg>
  );
}
