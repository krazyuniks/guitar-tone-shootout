import { createRouter } from '@tanstack/react-router'
import { rootRoute } from './routes/__root'
import { indexRoute } from './routes/index'
import { buildRoute } from './routes/build'
import { shootoutsRoute } from './routes/shootouts'
import { libraryRoute } from './routes/library'

const routeTree = rootRoute.addChildren([
  indexRoute,
  buildRoute,
  shootoutsRoute,
  libraryRoute,
])

export const router = createRouter({
  routeTree,
  basepath: '/app',
})

// Register the router instance for type safety
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
