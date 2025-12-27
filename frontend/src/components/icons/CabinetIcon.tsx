import * as React from "react";
import { cn } from "@/lib/utils";

interface CabinetIconProps extends React.SVGProps<SVGSVGElement> {
  className?: string;
}

/**
 * Cabinet/IR Icon - Speaker cabinet visual
 * Color: Green #22c55e (--color-block-cab)
 * Represents cabinet/impulse response blocks in the signal chain
 */
export function CabinetIcon({ className, ...props }: CabinetIconProps) {
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
      {/* Cabinet body */}
      <rect x="3" y="2" width="18" height="20" rx="2" />
      {/* 4x12 speaker arrangement (2x2 grid) */}
      <circle cx="9" cy="8" r="3" />
      <circle cx="15" cy="8" r="3" />
      <circle cx="9" cy="16" r="3" />
      <circle cx="15" cy="16" r="3" />
      {/* Speaker cone centers */}
      <circle cx="9" cy="8" r="1" fill="currentColor" />
      <circle cx="15" cy="8" r="1" fill="currentColor" />
      <circle cx="9" cy="16" r="1" fill="currentColor" />
      <circle cx="15" cy="16" r="1" fill="currentColor" />
    </svg>
  );
}
