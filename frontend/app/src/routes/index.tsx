import { createRoute } from '@tanstack/react-router'
import { rootRoute } from './__root'

export const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: function IndexPage() {
    return (
      <div data-testid="page-home">
        <h1 className="text-2xl font-semibold text-text-primary mb-2">GTS App</h1>
        <p className="text-text-secondary">
          Welcome to the Guitar Tone Shootout workspace.
        </p>
      </div>
    )
  },
})
