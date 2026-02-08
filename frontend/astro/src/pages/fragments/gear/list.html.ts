/**
 * fragments/gear/list.html.ts - Outputs dist/fragments/gear/list.html
 *
 * Gear list fragment for HTMX updates (filter/search results).
 */

import type { APIRoute } from 'astro';

import '../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `{% for gear in gear_items %}
<div data-testid="gear-item" class="p-4 border border-[var(--border)] rounded-lg mb-2">
  <h3 class="font-medium text-[var(--color-text-primary)]">{{ gear.name }}</h3>
  <span class="text-sm text-[var(--color-text-secondary)]">{{ gear.gear_type }}</span>
  {% if gear.manufacturer %}<span class="text-sm text-[var(--color-text-muted)]">{{ gear.manufacturer }}</span>{% endif %}
</div>
{% else %}
<div data-testid="empty-state" class="text-center py-8 text-[var(--color-text-muted)]">
  <p>No gear found. Try adjusting your filters.</p>
</div>
{% endfor %}
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
