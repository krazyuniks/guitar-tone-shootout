# Testability Requirements

All interactive elements MUST have `data-testid` attributes for Playwright testing.

## Required Attributes

```html
<!-- Page container -->
<div data-testid="gear-library">

<!-- List containers -->
<div data-testid="shootout-list">

<!-- List items with entity identity -->
<div data-testid="item-card" data-item-id="{{ item.id }}">

<!-- Action buttons -->
<button data-testid="item-card-delete-btn">

<!-- Form inputs -->
<input data-testid="form-email-input">

<!-- Tabs -->
<button data-testid="tab-browse">

<!-- HTMX containers -->
<div id="my-gear-results" data-testid="my-gear-results" hx-get="/api/v1/html/my-gear/results">
```

## State Exposure

Containers with loading/error/empty states MUST expose them:

```html
<div
  data-testid="item-list"
  data-loading="{{ 'true' if loading else 'false' }}"
  data-error="{{ 'true' if error else 'false' }}"
  data-empty="{{ 'true' if not items else 'false' }}"
>
```

## Test ID Naming Convention

| Pattern | Example |
|---------|---------|
| `{page}` | `gear-library`, `browse-page` |
| `{component}` | `shootout-card`, `chain-item` |
| `{component}-{element}` | `shootout-card-title` |
| `{component}-{action}-btn` | `shootout-card-delete-btn` |
| `{component}-{field}-input` | `login-email-input` |
| `{component}-list` | `shootout-list` |
| `tab-{name}` | `tab-browse`, `tab-my-gear` |

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

<!-- BAD: Index-based -->
data-testid="item-{{ loop.index }}"

<!-- GOOD: Entity-based -->
data-item-id="{{ item.id }}"

<!-- BAD: HTMX container without test ID -->
<div id="items" hx-get="/api/v1/html/items">

<!-- GOOD: HTMX container with test ID -->
<div id="items" data-testid="items-container" hx-get="/api/v1/html/items">
```
