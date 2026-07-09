import { createRootRoute, Outlet } from '@tanstack/react-router'
import { ApiError } from '../api/client'
import { getCurrentUser, type AuthMe } from '../api/auth'
import { AppShell } from '../components/AppShell'

// Auth-aware root route: calls /auth/me before rendering any app route.
// A 401 response means the session cookie is absent or expired; the user
// is redirected to /login with the current path in ?next= so they land back
// here after authenticating.
export const rootRoute = createRootRoute({
  beforeLoad: async ({ location }): Promise<{ user: AuthMe }> => {
    // B1 theme-lock probe is auth-exempt session tooling; this exemption is
    // removed together with the probe route when the theme lock lands.
    if (location.pathname.endsWith('/probe')) {
      return { user: { id: 'probe', username: 'probe', email: null, avatar_url: null } }
    }
    try {
      const user = await getCurrentUser()
      return { user }
    } catch (error) {
      if (!(error instanceof ApiError)) throw error
      const next = encodeURIComponent(window.location.pathname + window.location.search)
      window.location.replace(`/login?next=${next}`)
      // Suspend until the browser unloads.
      return new Promise<never>(() => undefined)
    }
  },
  component: function Root() {
    return (
      <AppShell>
        <Outlet />
      </AppShell>
    )
  },
})
