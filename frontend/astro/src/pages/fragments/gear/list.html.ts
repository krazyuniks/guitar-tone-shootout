/**
 * fragments/gear/list.html.ts - Outputs dist/fragments/gear/list.html
 *
 * Gear list fragment for HTMX updates via /api/v1/html/gear/list.
 * This is a Jinja2 fragment template.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `<!-- Gear List Fragment - HTMX response for /api/v1/html/gear/list -->
<div data-testid="gear-list-fragment">
  {% if gear_items %}
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
    {% for gear in gear_items %}
    <div data-testid="gear-list-item" class="border border-[var(--border)] rounded-lg p-4">
      <span class="font-medium">{{ gear.name }}</span>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <div data-testid="gear-list-empty" class="text-center py-8 text-[var(--color-text-muted)]">
    No gear found.
  </div>
  {% endif %}
</div>
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
