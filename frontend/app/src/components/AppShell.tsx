import { type ReactNode } from 'react'
import { Link } from '@tanstack/react-router'

interface Props {
  children: ReactNode
}

// Placeholder app shell — real Dense AppShell lands in slice B2.
export function AppShell({ children }: Props) {
  return (
    <div className="min-h-screen bg-bg-base text-text-primary flex flex-col" data-testid="app-shell">
      <nav
        className="border-b border-border bg-bg-surface px-4 py-3 flex items-center gap-6 shrink-0"
        data-testid="app-nav"
      >
        <span className="font-semibold text-text-primary">GTS</span>
        <Link
          to="/"
          className="text-text-secondary hover:text-text-primary transition-colors"
          data-testid="nav-home"
        >
          Home
        </Link>
        <Link
          to="/build"
          className="text-text-secondary hover:text-text-primary transition-colors"
          data-testid="nav-build"
        >
          Build
        </Link>
        <Link
          to="/shootouts"
          className="text-text-secondary hover:text-text-primary transition-colors"
          data-testid="nav-shootouts"
        >
          Shootouts
        </Link>
        <Link
          to="/library"
          className="text-text-secondary hover:text-text-primary transition-colors"
          data-testid="nav-library"
        >
          Library
        </Link>
      </nav>
      <main className="flex-1 p-4" data-testid="app-main">
        {children}
      </main>
    </div>
  )
}
