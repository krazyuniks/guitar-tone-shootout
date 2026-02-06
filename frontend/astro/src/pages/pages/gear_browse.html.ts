/**
 * Gear Browse Page Template
 *
 * Public-facing gear browse page with filtering and search.
 * Full page template served by FastAPI's Jinja2 renderer.
 *
 * Build output: frontend/astro/dist/pages/gear_browse.html
 * FastAPI route: templates.TemplateResponse(request, "pages/gear_browse.html", {...})
 */

export async function GET() {
  const html = `{% extends "layouts/base.html" %}

{% block title %}Browse Gear - Guitar Tone Shootout{% endblock %}

{% block content %}
<div
  data-testid="gear-browse-page"
  class="container mx-auto px-4 py-8"
>
  <h1
    data-testid="gear-browse-heading"
    class="text-[var(--color-text-primary)] text-3xl font-bold mb-6"
  >
    Browse Gear
  </h1>

  <!-- Filter Controls -->
  <div class="mb-6 flex flex-wrap gap-4">
    <!-- Search Input -->
    <div class="flex-1 min-w-[200px]">
      <input
        type="text"
        data-testid="gear-search-input"
        placeholder="Search gear..."
        class="w-full px-4 py-2 bg-[var(--color-bg-elevated)] text-[var(--color-text-primary)] border border-[var(--color-border)] rounded-lg"
        hx-get="/fragments/gear/list"
        hx-trigger="keyup changed delay:300ms"
        hx-target="#gear-list-container"
        hx-swap="innerHTML"
        hx-include="[data-testid='gear-type-filter'], [data-testid='manufacturer-filter']"
        name="query"
      />
    </div>

    <!-- Type Filter -->
    <div class="min-w-[150px]">
      <select
        data-testid="gear-type-filter"
        class="w-full px-4 py-2 bg-[var(--color-bg-elevated)] text-[var(--color-text-primary)] border border-[var(--color-border)] rounded-lg"
        hx-get="/fragments/gear/list"
        hx-trigger="change"
        hx-target="#gear-list-container"
        hx-swap="innerHTML"
        hx-include="[data-testid='gear-search-input'], [data-testid='manufacturer-filter']"
        name="gear_type"
      >
        <option value="">All Types</option>
        <option value="amp">Amps</option>
        <option value="pedal">Pedals</option>
        <option value="ir">IRs</option>
      </select>
    </div>

    <!-- Manufacturer Filter -->
    <div class="min-w-[150px]">
      <input
        type="text"
        data-testid="manufacturer-filter"
        placeholder="Manufacturer"
        class="w-full px-4 py-2 bg-[var(--color-bg-elevated)] text-[var(--color-text-primary)] border border-[var(--color-border)] rounded-lg"
        hx-get="/fragments/gear/list"
        hx-trigger="keyup changed delay:300ms"
        hx-target="#gear-list-container"
        hx-swap="innerHTML"
        hx-include="[data-testid='gear-search-input'], [data-testid='gear-type-filter']"
        name="manufacturer"
      />
    </div>
  </div>

  <!-- Gear List Container -->
  <div
    id="gear-list-container"
    data-testid="gear-list-container"
    hx-get="/fragments/gear/list"
    hx-trigger="load"
    hx-swap="innerHTML"
  >
    <!-- Loading skeleton -->
    <div class="animate-pulse">
      <div class="h-32 bg-[var(--color-bg-elevated)] rounded-lg mb-4"></div>
      <div class="h-32 bg-[var(--color-bg-elevated)] rounded-lg mb-4"></div>
      <div class="h-32 bg-[var(--color-bg-elevated)] rounded-lg mb-4"></div>
    </div>
  </div>
</div>
{% endblock %}
`;

  return new Response(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
}
