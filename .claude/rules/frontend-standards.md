# Frontend Standards Rules

## Hard Constraints

- **Pre-bundled:** `astro/dist/` is committed to git. Chokidar auto-rebuilds on source changes. Commit both `astro/src/` and `astro/dist/`.
- **All interactive elements MUST have `data-testid` attributes** for Playwright testing.
- **Links to SSR pages need `data-astro-reload`** in Astro components (ClientRouter intercepts clicks).
- **No CDN Tailwind.** All styles pre-compiled by Astro at `/_astro/*.css`.
- **Jinja2 templates extend `layouts/base.html`** (built by Astro, provides CSS + scripts).
- **No inline styles.** Use Tailwind utility classes with design tokens from `astro/src/styles/global.css`.

## SSR Routes (require `data-astro-reload`)

`/gear/*`, `/shootouts`, `/library/*`, `/shootout/*`, `/chain/*`

For detailed patterns (templates, HTMX mapping, testability, navigation), see the `gts-frontend-dev` skill.
