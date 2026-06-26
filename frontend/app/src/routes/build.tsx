import { createRoute } from '@tanstack/react-router'
import { rootRoute } from './__root'

export const buildRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/build',
  component: function BuildPage() {
    return (
      <div data-testid="page-build">
        <h1 className="text-2xl font-semibold text-text-primary mb-2">Signal Chain Builder</h1>
        <p className="text-text-secondary">
          Builder workspace — coming in a later epic slice.
        </p>
      </div>
    )
  },
})
