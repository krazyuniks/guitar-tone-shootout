/**
 * fragments/gear/card.html.ts - Outputs dist/fragments/gear/card.html
 *
 * Individual gear card fragment for HTMX updates.
 */

import type { APIRoute } from 'astro';

import '../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `<div data-testid="gear-card" class="rounded-lg border border-[var(--border)] p-4 bg-[var(--color-bg-elevated)]">
  <h3 class="font-medium text-[var(--color-text-primary)]">{{ gear.name }}</h3>
  <span class="text-sm text-[var(--color-text-secondary)]">{{ gear.gear_type }}</span>
</div>
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
