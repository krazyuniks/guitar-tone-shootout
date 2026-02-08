/**
 * fragments/chains/list.html.ts - Outputs dist/fragments/chains/list.html
 *
 * Chain list fragment for HTMX partial page updates.
 */

import type { APIRoute } from 'astro';

import '../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `{% if chains %}
<div class="space-y-3">
  {% for chain in chains %}
  <div data-testid="chain-item" class="bg-[var(--color-bg-elevated)] rounded-lg p-4">
    <div class="flex items-start justify-between">
      <div class="flex-1">
        <h3 class="font-medium text-[var(--color-text-primary)]">{{ chain.name }}</h3>
        {% if chain.description %}
        <p class="text-sm text-[var(--color-text-secondary)] mt-1">{{ chain.description }}</p>
        {% endif %}
        <div class="flex items-center gap-2 mt-2">
          <span data-testid="platform-badge" class="text-xs px-2 py-0.5 rounded bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)]">{{ chain.platform }}</span>
        </div>
      </div>
      <div class="flex items-center gap-2 ml-4">
        <a href="/library/chains/build?chain_id={{ chain.id }}" data-testid="edit-chain-btn" class="text-sm text-[var(--color-accent-primary)] hover:underline">Edit</a>
        <button data-testid="duplicate-chain-btn" hx-post="/fragments/chains/{{ chain.id }}/duplicate" class="text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]">Duplicate</button>
        <button data-testid="delete-chain-btn" hx-delete="/fragments/chains/{{ chain.id }}" hx-confirm="Delete this chain?" class="text-sm text-red-500 hover:text-red-400">Delete</button>
      </div>
    </div>
  </div>
  {% endfor %}
</div>
{% else %}
<div class="text-center py-12 text-[var(--color-text-secondary)]">
  <p>No chains yet. Create a chain to get started.</p>
</div>
{% endif %}
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
