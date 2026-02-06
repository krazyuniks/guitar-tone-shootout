/**
 * User Gear Library Page Template
 *
 * Protected page showing user's personal gear collection.
 * Full page template served by FastAPI's Jinja2 renderer.
 *
 * Build output: frontend/astro/dist/pages/library/my_gear.html
 * FastAPI route: templates.TemplateResponse(request, "pages/library/my_gear.html", {...})
 */

export async function GET() {
  const html = `{% extends "layouts/base.html" %}

{% block title %}My Gear - Guitar Tone Shootout{% endblock %}

{% block content %}
<div
  data-testid="library-my-gear-page"
  class="container mx-auto px-4 py-8"
>
  <div class="flex justify-between items-center mb-6">
    <h1
      class="text-[var(--color-text-primary)] text-3xl font-bold"
    >
      My Gear
    </h1>
    <button
      data-testid="add-gear-btn"
      class="px-4 py-2 bg-[var(--color-primary)] text-white rounded-lg hover:opacity-90"
      hx-get="/fragments/library/add-gear-form"
      hx-target="#modal-container"
      hx-swap="innerHTML"
    >
      Add Gear
    </button>
  </div>

  <!-- Filter Controls -->
  <div class="mb-6">
    <select
      data-testid="gear-type-filter"
      class="px-4 py-2 bg-[var(--color-bg-elevated)] text-[var(--color-text-primary)] border border-[var(--color-border)] rounded-lg"
      hx-get="/fragments/library/my-gear-list"
      hx-trigger="change"
      hx-target="#gear-list-container"
      hx-swap="innerHTML"
      name="gear_type"
    >
      <option value="">All Types</option>
      <option value="amp">Amps</option>
      <option value="pedal">Pedals</option>
      <option value="ir">IRs</option>
    </select>
  </div>

  <!-- Gear List Container -->
  <div id="gear-list-container" class="space-y-4">
    {% if gear_items %}
      {% for item in gear_items %}
        <div
          data-testid="gear-item"
          class="bg-[var(--color-bg-elevated)] rounded-lg p-4 flex justify-between items-center border border-[var(--color-border)]"
        >
          <div class="flex-1">
            <h3 class="text-[var(--color-text-primary)] font-semibold text-lg">
              {{ item.nickname or item.gear_name }}
            </h3>
            {% if item.nickname %}
              <p class="text-[var(--color-text-secondary)] text-sm">{{ item.gear_name }}</p>
            {% endif %}
            <p class="text-[var(--color-text-secondary)] text-sm">
              {{ item.gear_type }} • {{ item.manufacturer }}
            </p>
          </div>
          <button
            data-testid="remove-gear-btn"
            class="px-3 py-1 text-[var(--color-error)] hover:bg-[var(--color-bg-base)] rounded"
            hx-delete="/api/v1/library/gear/{{ item.user_gear_id }}"
            hx-confirm="Remove this gear from your library?"
            hx-target="closest [data-testid='gear-item']"
            hx-swap="outerHTML swap:0.3s"
          >
            Remove
          </button>
        </div>
      {% endfor %}
    {% else %}
      <div class="text-center py-12">
        <p class="text-[var(--color-text-secondary)] text-lg mb-4">
          No gear in your library yet
        </p>
        <p class="text-[var(--color-text-secondary)] text-sm">
          Click "Add Gear" to start building your collection
        </p>
      </div>
    {% endif %}
  </div>
</div>

<!-- Modal container for HTMX fragments -->
<div id="modal-container"></div>
{% endblock %}
`;

  return new Response(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
}
