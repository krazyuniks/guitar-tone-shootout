/**
 * fragments/shootouts/create/chain-list.html.ts - Outputs dist/fragments/shootouts/create/chain-list.html
 *
 * Chain list partial for shootout create wizard Step 1.
 * Displays selectable signal chains from user's library.
 * This is a Jinja2 fragment template.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `<!-- Chain List Partial for Shootout Create Wizard -->
{% if chains %}
  <div class="space-y-2 max-h-[400px] overflow-y-auto pr-2">
    {% for chain in chains %}
      <button
        type="button"
        @click="toggleChain('{{ chain.id }}', '{{ chain.name | e }}', {{ chain.block_count }}, '{{ chain.platform }}')"
        :class="{
          'border-[var(--color-accent-primary)] bg-[var(--color-accent-primary)]/10': isChainSelected('{{ chain.id }}'),
          'border-border hover:border-[var(--color-accent-primary)]/50': !isChainSelected('{{ chain.id }}')
        }"
        class="w-full p-4 rounded-lg border text-left transition-all"
        data-testid="chain-option"
        data-chain-id="{{ chain.id }}"
      >
        <div class="flex items-center justify-between">
          <div>
            <div class="font-medium">{{ chain.name }}</div>
            <div class="text-sm text-[var(--color-text-secondary)]">
              {{ chain.block_count }} {{ 'block' if chain.block_count == 1 else 'blocks' }} ·
              {% if chain.platform == 'nam' %}NAM{% elif chain.platform == 'aida_x' %}AIDA-X{% else %}{{ chain.platform.upper() }}{% endif %}
            </div>
          </div>
          <svg
            x-show="isChainSelected('{{ chain.id }}')"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            class="w-5 h-5 text-[var(--color-accent-primary)]"
          >
            <path
              fill-rule="evenodd"
              d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
              clip-rule="evenodd"
            />
          </svg>
        </div>
      </button>
    {% endfor %}
  </div>
{% else %}
  <div class="text-center py-8">
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="currentColor"
      class="w-12 h-12 text-[var(--color-accent-primary)] mx-auto"
    >
      <path
        fill-rule="evenodd"
        d="M19.902 4.098a3.75 3.75 0 00-5.304 0l-4.5 4.5a3.75 3.75 0 001.035 6.037.75.75 0 01-.646 1.353 5.25 5.25 0 01-1.449-8.45l4.5-4.5a5.25 5.25 0 117.424 7.424l-1.757 1.757a.75.75 0 11-1.06-1.06l1.757-1.758a3.75 3.75 0 000-5.303zm-7.389 4.267a.75.75 0 011-.353 5.25 5.25 0 011.449 8.45l-4.5 4.5a5.25 5.25 0 11-7.424-7.424l1.757-1.757a.75.75 0 111.06 1.06l-1.757 1.757a3.75 3.75 0 105.304 5.304l4.5-4.5a3.75 3.75 0 00-1.035-6.037.75.75 0 01-.354-1z"
        clip-rule="evenodd"
      />
    </svg>
    <p class="text-[var(--color-text-secondary)] mt-4">
      {% if search %}No chains match your search{% else %}No signal chains in library{% endif %}
    </p>
    {% if not search %}
      <a
        href="/library/chains/build"
        data-astro-reload
        class="inline-flex items-center px-4 py-2 mt-4 border border-border rounded-md text-sm font-medium hover:bg-muted transition-colors"
      >
        Create Signal Chain
      </a>
    {% endif %}
  </div>
{% endif %}
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
