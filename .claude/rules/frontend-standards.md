# Frontend Standards Rules

## Hard Constraints

- **Pre-bundled:** `astro/dist/` is committed to git. Chokidar auto-rebuilds on source changes. Commit both `astro/src/` and `astro/dist/`.
- **All interactive elements MUST have `data-testid` attributes** for Playwright testing.
- **No CDN Tailwind.** All styles pre-compiled by Astro at `/_astro/*.css`.
- **Jinja2 templates extend `layouts/base.html`** (built by Astro, provides CSS + scripts).
- **No inline styles.** Use Tailwind utility classes with design tokens from `astro/src/styles/global.css`.
- **No SPA navigation.** All links are standard `<a href>` — no ClientRouter, no View Transitions, no `data-astro-reload`.
- **HTMX for small interactions only** (checkboxes, modals, inline updates). Not for page navigation.

For detailed patterns (templates, HTMX mapping, testability, navigation), see the `gts-frontend-dev` skill.
