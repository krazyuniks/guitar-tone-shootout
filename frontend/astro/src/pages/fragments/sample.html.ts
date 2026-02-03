/**
 * Sample Fragment Template
 *
 * This demonstrates the pattern for HTMX response fragments.
 * These are HTML snippets returned by API endpoints for dynamic updates.
 *
 * Build output: frontend/astro/dist/fragments/sample.html
 * FastAPI route: templates.TemplateResponse(request, "fragments/sample.html", {...})
 * HTMX usage: hx-get="/api/v1/html/sample/content"
 */

export async function GET() {
  const html = `<!-- Sample Fragment: List of items -->
{% for item in items %}
<div
  data-testid="item-card"
  data-item-id="{{ item.id }}"
  class="bg-[var(--color-bg-elevated)] rounded-lg p-4 mb-4"
>
  <h3
    data-testid="item-card-title"
    class="text-[var(--color-text-primary)] font-semibold mb-2"
  >
    {{ item.name }}
  </h3>

  <p
    data-testid="item-card-description"
    class="text-[var(--color-text-secondary)] mb-4"
  >
    {{ item.description }}
  </p>

  <!-- Action buttons -->
  <div class="flex gap-2">
    <button
      data-testid="item-card-edit-btn"
      hx-get="/api/v1/html/items/{{ item.id }}/edit"
      hx-target="closest [data-testid='item-card']"
      hx-swap="outerHTML"
      class="bg-[var(--color-accent-primary)] text-white px-4 py-2 rounded-lg"
    >
      Edit
    </button>

    <button
      data-testid="item-card-delete-btn"
      hx-delete="/api/v1/html/items/{{ item.id }}"
      hx-target="closest [data-testid='item-card']"
      hx-swap="outerHTML"
      hx-confirm="Delete this item?"
      class="bg-[var(--color-accent-error)] text-white px-4 py-2 rounded-lg"
    >
      Delete
    </button>
  </div>
</div>
{% endfor %}

{% if not items %}
<div
  data-testid="empty-state"
  class="text-center py-8 text-[var(--color-text-muted)]"
>
  <p>No items found.</p>
</div>
{% endif %}
`;

  return new Response(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
}
