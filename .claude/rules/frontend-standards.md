# Frontend Standards Rules

For full documentation, see [Frontend Development Standards](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Frontend-Development-Standards) in the GitHub Wiki.

## Pre-Bundled Architecture

**Astro is pre-bundled.** `astro/dist/` is committed to git. No Vite dev server at runtime.

| Component | Purpose |
|-----------|---------|
| `astro/dist/` | Pre-built Astro output (committed to git) |
| nginx | Serves static files from bind-mounted `astro/dist/` |
| FastAPI | Serves SSR pages using Jinja2 templates |

**Development workflow:**
1. Edit source in `astro/src/`
2. Run `just build-astro` (or `just watch-astro` for auto-rebuild)
3. Commit both `astro/src/` and `astro/dist/`

### Sync Verification

**CI enforces sync between `astro/src/` and `astro/dist/`.** PRs fail if dist/ is out of sync.

```bash
# Verify before committing
just verify-astro-sync
```

This builds Astro and checks for uncommitted changes in dist/. If the check fails:
1. Changes were made to `astro/src/` without rebuilding
2. Run `just build-astro`
3. Commit the updated `astro/dist/` files

**Why this matters:**
- Pre-bundled architecture relies on committed dist/ for CI and production
- Out-of-sync dist/ means production differs from development
- Automated verification prevents accidental drift

## Route Architecture

| Route Type | Technology | Example |
|------------|------------|---------|
| Static pages | Astro SSG (pre-built) + nginx | `/`, `/about`, `/login` |
| Dynamic pages | Jinja2 + FastAPI | `/library/*`, `/shootouts`, `/gear/*`, `/shootout/*` |
| Complex UI | React island | `/library/chains/build` (SignalChainBuilder only) |

## Navigation Between Static and SSR Pages

**CRITICAL:** Astro's `<ClientRouter />` intercepts all link clicks for SPA-like transitions. SSR pages (Jinja2) require full page navigation.

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

## Styling Jinja2 Templates

**Design tokens and styles come from Astro.** Jinja2 templates extend an Astro-built base layout and use Tailwind class names.

### Key Principles

1. **Base layout from Astro** - `astro/dist/layouts/base.html` provides the HTML shell with CSS
2. **Use Tailwind classes** - Defined in `astro/src/styles/global.css`, compiled by Astro
3. **No inline styles** - Use Tailwind utility classes instead
4. **No CDN Tailwind** - CSS is pre-compiled at `/_astro/*.css` and loaded by the wrapper
5. **Consistent with static pages** - Same design tokens, same Tailwind config

### How It Works

**Build process:**
```
astro/src/styles/global.css (design tokens)
astro/src/layouts/BaseWrapper.astro (layout source)
    ↓ Astro build
astro/dist/_astro/*.css (compiled CSS)
astro/dist/layouts/base.html (Jinja2 wrapper template)
    ↓ Jinja2 extends
Dynamic pages use same CSS as static pages
```

**Jinja2 templates extend the Astro-built wrapper:**
```jinja2
{% extends "layouts/base.html" %}

{% block content %}
<div class="bg-[var(--color-bg-elevated)] rounded-lg p-4">
  <h3 class="text-[var(--color-text-primary)] font-semibold">
    {{ pack.name }}
  </h3>
</div>
{% endblock %}
```

**CSS is pre-loaded by the wrapper - no manual stylesheet links needed.**

### Design Token Reference

Use CSS custom properties from Astro:
- `--color-bg-base`, `--color-bg-surface`, `--color-bg-elevated` (backgrounds)
- `--color-text-primary`, `--color-text-secondary`, `--color-text-muted` (text)
- `--color-accent-primary`, `--color-accent-success`, etc. (accents)
- `--color-block-amp`, `--color-block-pedal`, etc. (gear type colors)

**Example:**
```html
<button class="bg-[var(--color-accent-primary)] text-white px-4 py-2 rounded-lg">
  Save
</button>
```

### When Changing Design

1. Edit `astro/src/styles/global.css` (single source of truth)
2. Run `just build-astro` (or use `just watch-astro` for auto-rebuild)
3. Changes apply to both static AND dynamic pages automatically
4. No need to touch Jinja2 templates
5. No backend restart needed - templates auto-reload from disk

### Wrapper Architecture

The Astro-built wrapper (`astro/dist/layouts/base.html`) provides:
- HTML document structure with `<head>` and `<body>`
- Pre-compiled CSS link to `/_astro/*.css`
- HTMX and Alpine.js script tags
- Jinja2 blocks (`{% block content %}`, `{% block scripts %}`) for page content

## Testability Requirements

**CRITICAL:** All interactive elements MUST have `data-testid` attributes for Playwright testing.

### Required on ALL Interactive Elements

```html
<!-- Page container -->
<div data-testid="gear-library">

<!-- List containers -->
<div data-testid="shootout-list">

<!-- List items with entity identity -->
<div
  data-testid="item-card"
  data-item-id="{{ item.id }}"
>

<!-- Action buttons -->
<button data-testid="item-card-delete-btn">

<!-- Form inputs -->
<input data-testid="form-email-input">

<!-- Tabs -->
<button data-testid="tab-browse">
<button data-testid="tab-my-gear">

<!-- HTMX containers -->
<div
  id="my-gear-results"
  data-testid="my-gear-results"
  hx-get="/api/v1/html/my-gear/results"
>
```

### State Exposure

Containers with loading/error/empty states MUST expose them:

```html
<div
  data-testid="item-list"
  data-loading="{{ 'true' if loading else 'false' }}"
  data-error="{{ 'true' if error else 'false' }}"
  data-empty="{{ 'true' if not items else 'false' }}"
>
```

### Test ID Naming Convention

| Pattern | Example |
|---------|---------|
| `{page}` | `gear-library`, `browse-page` |
| `{component}` | `shootout-card`, `chain-item` |
| `{component}-{element}` | `shootout-card-title` |
| `{component}-{action}-btn` | `shootout-card-delete-btn` |
| `{component}-{field}-input` | `login-email-input` |
| `{component}-list` | `shootout-list` |
| `tab-{name}` | `tab-browse`, `tab-my-gear` |

## Template File Structure

**All templates are authored as TypeScript files (.html.ts)** in `astro/src/pages/`. Astro builds these to `astro/dist/` which is committed to git.

```
astro/src/pages/               # Template source files (.html.ts)
├── layouts/
│   └── base.astro                # Base layout wrapper
├── partials/
│   ├── header.html.ts            # Nav with auth state
│   └── footer.html.ts
├── pages/                        # Full page templates
│   ├── gear.html.ts              # /gear/{slug} - Public pack detail
│   ├── gear_browse.html.ts       # /gear - Browse gear packs
│   ├── shootouts.html.ts         # /shootouts - Shootout listing
│   ├── shootout_detail.html.ts   # /shootout/{id} - Shootout detail
│   └── library/                  # User library pages
│       └── my_gear.html.ts       # /library/my-gear
├── fragments/                    # HTMX response templates
│   ├── gear/                     # Gear fragments
│   │   └── public_browse.html.ts
│   ├── library/                  # Library fragments
│   │   └── my_gear.html.ts
│   └── shootouts/                # Shootout fragments
│       └── list.html.ts
└── [.astro files]                # Static pages (index, about, login, etc.)

astro/dist/                    # Build output (COMMITTED TO GIT)
├── layouts/
│   └── base.html                 # Built Jinja2 wrapper
├── pages/, fragments/, partials/ # Built .html templates
├── _astro/
│   └── *.css                     # Compiled Tailwind CSS
└── *.html                        # Static pages (home, about, login, etc.)
```

**Build process:** `just build-astro` compiles `.html.ts` files to `.html` in `astro/dist/`.

**Template resolution:** FastAPI's Jinja2 template loader reads from `astro/dist/`.

**nginx serves static files** directly from the bind-mounted `astro/dist/` directory.

## Page Template Pattern

```html
{% extends "layouts/base.html" %}

{% block title %}Page Title{% endblock %}

{% block content %}
<div
  data-testid="page-name"
  class="container mx-auto px-4 py-8"
  x-data="{ /* Alpine.js state */ }"
>
  <!-- HTMX container with loading skeleton -->
  <div
    id="content-container"
    data-testid="content-container"
    hx-get="/api/v1/html/content"
    hx-trigger="load"
    hx-swap="innerHTML"
  >
    <div class="animate-pulse">Loading...</div>
  </div>
</div>
{% endblock %}

{% block scripts %}
<script>
  // Handle auth errors from HTMX requests
  document.body.addEventListener('htmx:responseError', (event) => {
    if (event.detail?.xhr?.status === 401) {
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    }
  });
</script>
{% endblock %}
```

## Fragment Template Pattern

```html
<!-- fragments/library/item_card.html -->
{% for item in items %}
<div
  data-testid="item-card"
  data-item-id="{{ item.id }}"
  class="bg-bg-elevated rounded-lg p-4"
>
  <h3 data-testid="item-card-title">{{ item.name }}</h3>
  <button
    data-testid="item-card-delete-btn"
    hx-delete="/api/v1/html/items/{{ item.id }}"
    hx-target="closest [data-testid='item-card']"
    hx-swap="outerHTML"
    hx-confirm="Delete this item?"
  >
    Delete
  </button>
</div>
{% endfor %}
```

## Anti-Patterns

```html
<!-- BAD: Missing test ID -->
<button hx-delete="/api/v1/html/items/123">Delete</button>

<!-- GOOD: Has test ID -->
<button data-testid="item-delete-btn" hx-delete="/api/v1/html/items/123">Delete</button>

<!-- BAD: Generic test ID -->
<button data-testid="button">Delete</button>

<!-- GOOD: Specific, scoped test ID -->
<button data-testid="item-card-delete-btn">Delete</button>

<!-- BAD: Index-based data attributes -->
data-testid="item-{{ loop.index }}"

<!-- GOOD: Entity-based data attributes -->
data-item-id="{{ item.id }}"

<!-- BAD: HTMX container without test ID -->
<div id="items" hx-get="/api/v1/html/items">

<!-- GOOD: HTMX container with test ID -->
<div id="items" data-testid="items-container" hx-get="/api/v1/html/items">
```

## HTMX Requirements

- All HTMX containers must have `data-testid` attributes
- Use `hx-confirm` for destructive actions
- Include loading skeletons in initial container state
- Handle 401 errors with auth redirect script

## HTMX Fragment Mapping

**Backend routes map to frontend templates by convention.**

### URL to Template Mapping

| Backend Route | Template Path | Purpose |
|---------------|---------------|---------|
| `/api/v1/html/sample` | `fragments/sample.html` | Sample/demo fragment |
| `/api/v1/html/ping` | `fragments/ping.html` | Health check fragment |
| `/api/v1/html/shootouts/sections` | `fragments/shootouts/sections.html` | Shootout sections |
| `/api/v1/html/shootouts/list` | `fragments/shootouts/list.html` | Shootout list |
| `/api/v1/html/library/shootouts` | `fragments/library/shootouts.html` | User's shootouts |
| `/api/v1/html/my-gear/results` | `fragments/library/my_gear.html` | User gear list |
| `/api/v1/html/gear/browse` | `fragments/gear/browse.html` | Browse gear |
| `/api/v1/html/library/chains` | `fragments/library/chains.html` | User's signal chains |
| `/api/v1/html/library/tracks` | `fragments/library/tracks.html` | User's DI tracks |
| `/api/v1/html/library/groups` | `fragments/library/groups.html` | User's chain groups |
| `/api/v1/html/di-tracks/browse` | `fragments/di-tracks/browse.html` | Browse DI tracks |

### Naming Convention

```
Backend: /api/v1/html/{domain}/{action}
Template: fragments/{domain}/{action}.html

Examples:
  /api/v1/html/gear/browse      → fragments/gear/browse.html
  /api/v1/html/library/chains   → fragments/library/chains.html
  /api/v1/html/shootouts/list   → fragments/shootouts/list.html
```

### Fragment Response Pattern

```python
# backend/app/api/v1/html.py
@router.get("/library/items", response_class=HTMLResponse)
async def get_items_fragment(
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    items = await fetch_items(db, user.id)
    return templates.TemplateResponse(
        request=request,
        name="fragments/library/items.html",
        context={"items": items, "user": user},
    )
```

### Page to Fragment Relationship

Pages load fragment content via HTMX on initial load:

```
Page: pages/library/my_gear.html
  ↓ hx-get="/api/v1/html/my-gear/results" hx-trigger="load"
Fragment: fragments/library/my_gear.html
```

### Adding New Fragments

1. Create template in `astro/src/pages/fragments/{domain}/{name}.html.ts`
2. Run `just build-astro` to compile to `astro/dist/fragments/{domain}/{name}.html`
3. Create backend endpoint in `backend/app/api/v1/html.py`
4. Add `data-testid` attributes to all interactive elements
5. Wire up HTMX attributes in the parent page

## Alpine.js Requirements

- Use for client-side UI state only (tabs, toggles, menus)
- Always define `x-data` with meaningful state names
- Use `x-show` with `x-transition` for smooth visibility changes

## React Islands (SignalChainBuilder Only)

React is used ONLY for the SignalChainBuilder component at `/library/chains/build`. All other pages use Jinja2 + HTMX.

```html
{% block scripts %}
<script src="/static/islands/signal-chain-builder.js"></script>
<script>
  window.SignalChainBuilder.mount('signal-chain-builder');
</script>
{% endblock %}
```

## Related

- [Frontend Architecture](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Frontend-Architecture) - Architecture overview
- [Frontend Development Standards](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Frontend-Development-Standards) - Coding standards
- `.claude/skills/frontend-dev/SKILL.md` - Development patterns
- `.claude/skills/htmx/SKILL.md` - HTMX patterns
