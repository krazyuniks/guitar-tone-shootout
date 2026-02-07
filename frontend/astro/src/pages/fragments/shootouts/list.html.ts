/**
 * fragments/shootouts/list.html.ts - Outputs dist/fragments/shootouts/list.html
 *
 * Shootout cards list fragment for HTMX partial updates (renamed from shootouts.html).
 * This is a Jinja2 fragment template.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `{# Shootout cards list fragment - for HTMX partial updates #}
<div data-testid="shootouts-list">
  {% if shootouts %}
    {% for shootout in shootouts %}
      {% include "fragments/shootouts/shootout_card.html" %}
    {% endfor %}
  {% else %}
    <div data-testid="shootouts-empty" class="text-center py-8 text-[var(--color-text-muted)]">
      No shootouts found.
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
