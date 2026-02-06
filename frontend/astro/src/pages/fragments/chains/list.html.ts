/**
 * Chain List Fragment Template
 *
 * HTMX fragment for displaying the list of user's signal chains.
 * Returns just the list of chain cards without page wrapper.
 *
 * Build output: frontend/astro/dist/fragments/chains/list.html
 * FastAPI route: templates.TemplateResponse(request, "fragments/chains/list.html", {"chains": chains})
 * HTMX usage: hx-get="/fragments/chains/list"
 */

export async function GET() {
  const html = `<!-- Chain List Fragment -->
{% if chains %}
<div class="space-y-4">
  {% for chain in chains %}
  {% include "fragments/chains/card.html" %}
  {% endfor %}
</div>
{% else %}
<div class="text-center py-12">
  <p class="text-[var(--color-text-secondary)] text-lg mb-4">
    No chains yet
  </p>
  <p class="text-[var(--color-text-secondary)] text-sm">
    Create your first signal chain to get started
  </p>
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
