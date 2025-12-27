/**
 * ConnectionLine - Visual connector between signal chain stages.
 *
 * Displays a horizontal line with an arrow to show signal flow direction.
 * Hidden on mobile where columns stack vertically.
 */
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ConnectionLineProps {
  /** Additional CSS classes */
  className?: string;
}

export function ConnectionLine({ className }: ConnectionLineProps) {
  return (
    <div
      className={cn(
        'hidden items-center justify-center lg:flex',
        'mx-2 flex-shrink-0',
        className
      )}
      aria-hidden="true"
    >
      {/* Line */}
      <div className="h-px w-6 bg-border" />
      {/* Arrow */}
      <ChevronRight className="h-4 w-4 -ml-1 text-muted-foreground" />
    </div>
  );
}
