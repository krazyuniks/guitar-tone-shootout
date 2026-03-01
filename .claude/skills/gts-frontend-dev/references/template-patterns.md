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
    hx-get="/api/html/content"
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
    hx-delete="/api/html/items/{{ item.id }}"
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
| `POST /api/html/gear/model/{id}/toggle` | `fragments/gear/model_row.html` | Toggle gear model save/unsave |
| `POST /api/html/gear/models/bulk-toggle` | (empty response) | Bulk toggle gear models |
| `POST /api/html/library/tracks/{id}/toggle-public` | `fragments/library/track_item.html` | Toggle track visibility |
| `POST /api/html/library/tracks/{id}/save` | (empty response) | Save track to library |
| `GET /api/html/shootout-create/chains` | `fragments/shootouts/create/chain-list.html` | Wizard chain picker |
| `GET /api/html/shootout-create/ditracks` | `fragments/shootouts/create/ditrack-list.html` | Wizard DI track picker |
| `POST /api/html/shootout-create` | (redirect on success) | Wizard form submit |
| `GET /api/html/shootouts/{id}/comments` | `fragments/shootouts/comments.html` | Comments section |
| `GET /api/html/jobs/{id}` | (inline HTML) | Job status polling |

### Naming Convention

```
Backend: /api/html/{domain}/{action}
Template: fragments/{domain}/{action}.html
```

### Adding New Fragments

1. Create template in `astro/src/pages/fragments/{domain}/{name}.html.ts`
2. Run `just build-astro` to compile to `astro/dist/fragments/{domain}/{name}.html`
3. Create backend endpoint in `apps/webapp/src/webapp/api/html.py`
4. Add `data-testid` attributes to all interactive elements
5. Wire up HTMX attributes in the parent page
