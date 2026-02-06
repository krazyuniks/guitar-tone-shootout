/**
 * Gear List Fragment Template
 *
 * HTMX fragment for dynamically updating gear list based on filters.
 * Returns just the list of gear cards without page wrapper.
 *
 * Build output: frontend/astro/dist/fragments/gear/list.html
 * FastAPI route: templates.TemplateResponse(request, "fragments/gear/list.html", {"gear_items": items})
 * HTMX usage: hx-get="/fragments/gear/list?query=...&gear_type=...&manufacturer=..."
 */

export async function GET() {
  const html = `<!-- Gear List Fragment -->
{% if gear_items %}
<div class="space-y-4">
  {% for gear in gear_items %}
  {% include "fragments/gear/card.html" %}
  {% endfor %}
</div>

<!-- Pagination info if needed -->
{% if total %}
<div class="mt-6 text-center text-[var(--color-text-secondary)]">
  Showing {{ gear_items|length }} of {{ total }} items
</div>
{% endif %}

{% else %}
<div
  data-testid="empty-state"
  class="text-center py-12 text-[var(--color-text-muted)]"
>
  <p class="text-lg mb-2">No gear found</p>
  <p class="text-sm">Try adjusting your filters</p>
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
