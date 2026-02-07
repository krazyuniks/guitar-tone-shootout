# Navigation

## Astro ClientRouter and SSR Pages

Astro's `<ClientRouter />` intercepts all link clicks for SPA-like transitions. SSR pages (Jinja2) require full page navigation.

### The Problem

Astro ClientRouter intercepts `<a>` clicks and fetches pages via AJAX. SSR pages served by FastAPI fail silently because Astro can't process them.

### The Solution

Add `data-astro-reload` to links that navigate from Astro pages to SSR pages:

```html
<!-- In Astro components (Header.astro) -->
<!-- Links to SSR pages MUST have data-astro-reload -->
<a href="/gear" data-astro-reload>Gear</a>
<a href="/shootouts" data-astro-reload>Shootouts</a>
<a href="/library/my-gear" data-astro-reload>My Gear</a>

<!-- Links to other Astro pages can use normal navigation -->
<a href="/about">About</a>
<a href="/login">Login</a>
```

### SSR Routes (require `data-astro-reload`)

- `/gear`, `/gear/*`
- `/shootouts`
- `/library/*`
- `/shootout/*`
- `/chain/*`

### Debugging Navigation Issues

If a link click does nothing:
1. Check browser console for JS errors
2. Verify the link has `data-astro-reload` if targeting an SSR page
3. Check Network tab - request should appear for full navigation
