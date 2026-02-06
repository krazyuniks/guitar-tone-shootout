/**
 * Chain Card Fragment Template
 *
 * Individual chain card component used in lists.
 * Can be used standalone or included in list fragments.
 *
 * Build output: frontend/astro/dist/fragments/chains/card.html
 * FastAPI route: templates.TemplateResponse(request, "fragments/chains/card.html", {"chain": chain})
 * Jinja2 include: {% include "fragments/chains/card.html" %}
 */

export async function GET() {
  const html = `<!-- Chain Card -->
<div
  data-testid="chain-item"
  data-chain-id="{{ chain.id }}"
  class="bg-[var(--color-bg-elevated)] rounded-lg p-6 hover:shadow-lg transition-shadow"
>
  <div class="flex justify-between items-start mb-4">
    <!-- Chain Info -->
    <div class="flex-1">
      <h3 class="text-[var(--color-text-primary)] font-bold text-xl mb-2">
        {{ chain.name }}
      </h3>

      {% if chain.description %}
      <p class="text-[var(--color-text-secondary)] text-sm line-clamp-2 mb-2">
        {{ chain.description }}
      </p>
      {% endif %}

      <!-- Platform Badge -->
      <span
        data-testid="platform-badge"
        class="inline-block bg-[var(--color-accent-primary)] text-white px-3 py-1 rounded text-sm"
      >
        {{ chain.platform.value }}
      </span>
    </div>
  </div>

  <!-- Actions -->
  <div class="flex gap-2 justify-end">
    <!-- Edit Link -->
    <a
      href="/library/chains/build?chain_id={{ chain.id }}"
      data-testid="edit-chain-btn"
      class="px-4 py-2 bg-[var(--color-bg-base)] text-[var(--color-text-primary)] rounded-lg hover:opacity-90"
    >
      Edit
    </a>

    <!-- Duplicate Button -->
    <button
      data-testid="duplicate-chain-btn"
      hx-post="/fragments/chains/{{ chain.id }}/duplicate"
      hx-target="#chain-list-container"
      hx-swap="innerHTML"
      class="px-4 py-2 bg-[var(--color-bg-base)] text-[var(--color-text-primary)] rounded-lg hover:opacity-90"
    >
      Duplicate
    </button>

    <!-- Delete Button -->
    <button
      data-testid="delete-chain-btn"
      hx-delete="/fragments/chains/{{ chain.id }}"
      hx-target="#chain-list-container"
      hx-swap="innerHTML"
      hx-confirm="Are you sure you want to delete this chain?"
      class="px-4 py-2 bg-red-600 text-white rounded-lg hover:opacity-90"
    >
      Delete
    </button>
  </div>
</div>
`;

  return new Response(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
}
