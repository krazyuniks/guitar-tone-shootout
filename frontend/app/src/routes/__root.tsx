import { createRootRoute, Outlet } from '@tanstack/react-router'
import { AppShell } from '../components/AppShell'

export type AuthUser = {
  id: string
  username: string
  email: string | null
  avatar_url: string | null
}

// Auth-aware root route: calls /auth/me before rendering any app route.
// A 401 response means the session cookie is absent or expired; the user
// is redirected to /login with the current path in ?next= so they land back
// here after authenticating.
export const rootRoute = createRootRoute({
  beforeLoad: async (): Promise<{ user: AuthUser }> => {
    const resp = await fetch('/auth/me')
    if (!resp.ok) {
      const next = encodeURIComponent(window.location.pathname + window.location.search)
      window.location.replace(`/login?next=${next}`)
      // Suspend until the browser unloads — never settles
      return new Promise<never>(() => undefined)
    }
    const user = (await resp.json()) as AuthUser
    return { user }
  },
  component: function Root() {
    return (
      <AppShell>
        <Outlet />
      </AppShell>
    )
  },
})
