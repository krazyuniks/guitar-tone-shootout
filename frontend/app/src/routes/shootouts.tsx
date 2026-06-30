import { createRoute } from '@tanstack/react-router'
import { rootRoute } from './__root'

export const shootoutsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/shootouts',
  component: function ShootoutsPage() {
    return (
      <div data-testid="page-shootouts">
        <h1 className="text-2xl font-semibold text-text-primary mb-2">My Shootouts</h1>
        <p className="text-text-secondary">
          Your shootout workspace — coming in a later epic slice.
        </p>
      </div>
    )
  },
})
