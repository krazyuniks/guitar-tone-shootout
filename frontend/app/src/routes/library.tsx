import { createRoute } from '@tanstack/react-router'
import { rootRoute } from './__root'

export const libraryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/library',
  component: function LibraryPage() {
    return (
      <div data-testid="page-library">
        <h1 className="text-2xl font-semibold text-text-primary mb-2">Library</h1>
        <p className="text-text-secondary">
          My DIs and My Gear — coming in a later epic slice.
        </p>
      </div>
    )
  },
})
