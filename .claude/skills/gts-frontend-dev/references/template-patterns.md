# Template Patterns

## Template File Structure

All templates authored as TypeScript files (`.html.ts`) in `astro/src/pages/`. Astro builds these to `astro/dist/`.

```
astro/src/pages/               # Template source files (.html.ts)
├── layouts/
│   └── base.astro                # Base layout wrapper
├── partials/
│   ├── header.html.ts            # Nav with auth state
│   └── footer.html.ts
├── pages/                        # Full page templates
│   ├── gear.html.ts              # /gear/{slug}
│   ├── gear_browse.html.ts       # /gear
│   ├── shootouts.html.ts         # /shootouts
│   ├── shootout_detail.html.ts   # /shootout/{id}
│   └── library/
│       └── my_gear.html.ts       # /library/my-gear
├── fragments/                    # HTMX response templates
│   ├── gear/
│   ├── library/
│   └── shootouts/
└── [.astro files]                # Static pages (index, about, login, etc.)
```

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

## HTMX Fragment Mapping

### URL to Template Mapping

| Backend Route | Template Path | Purpose |
|---------------|---------------|---------|
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
```

### Adding New Fragments

1. Create template in `astro/src/pages/fragments/{domain}/{name}.html.ts`
2. Run `just build-astro` to compile to `astro/dist/fragments/{domain}/{name}.html`
3. Create backend endpoint in `apps/webapp/src/webapp/api/v1/html.py`
4. Add `data-testid` attributes to all interactive elements
5. Wire up HTMX attributes in the parent page
