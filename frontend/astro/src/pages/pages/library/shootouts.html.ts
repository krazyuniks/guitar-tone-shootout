/**
 * Shootout Library Page Template
 *
 * Protected page showing user's shootouts.
 * Full page template served by FastAPI's Jinja2 renderer.
 *
 * Build output: frontend/astro/dist/pages/library/shootouts.html
 * FastAPI route: templates.TemplateResponse(request, "pages/library/shootouts.html", {...})
 */

export async function GET() {
  const html = `{% extends "layouts/base.html" %}

{% block title %}My Shootouts - Guitar Tone Shootout{% endblock %}

{% block content %}
<div
  data-testid="library-shootouts-page"
  class="container mx-auto px-4 py-8"
>
  <div class="flex justify-between items-center mb-6">
    <h1
      class="text-[var(--color-text-primary)] text-3xl font-bold"
    >
      My Shootouts
    </h1>
    <a
      href="/shootout/new"
      data-testid="create-shootout-btn"
      class="px-4 py-2 bg-[var(--color-primary)] text-white rounded-lg hover:opacity-90"
    >
      Create Shootout
    </a>
  </div>

  <!-- Shootout List Container -->
  <div
    id="shootout-list-container"
    hx-get="/fragments/shootouts/list"
    hx-trigger="load"
    hx-swap="innerHTML"
    class="space-y-4"
  >
    {% if shootouts %}
      {% for shootout in shootouts %}
        <div
          data-testid="shootout-item"
          class="bg-[var(--color-bg-elevated)] rounded-lg p-4 border border-[var(--color-border)]"
        >
          <div class="flex justify-between items-start mb-2">
            <div class="flex-1">
              <h3 class="text-[var(--color-text-primary)] font-semibold text-lg">
                {{ shootout.name }}
              </h3>
              {% if shootout.description %}
                <p class="text-[var(--color-text-secondary)] text-sm mt-1">
                  {{ shootout.description }}
                </p>
              {% endif %}
              <div class="text-[var(--color-text-secondary)] text-xs mt-2">
                {{ shootout.chain_count }} chains
                {% if shootout.is_processed %}
                  <span class="text-green-600 ml-2">• Processed</span>
                {% else %}
                  <span class="text-yellow-600 ml-2">• Pending</span>
                {% endif %}
              </div>
            </div>
          </div>
          <div class="flex justify-end gap-2 mt-3">
            <a
              href="/shootout/{{ shootout.id }}"
              data-testid="view-shootout-btn"
              class="px-3 py-1 text-[var(--color-primary)] hover:bg-[var(--color-bg-base)] rounded"
            >
              View
            </a>
            <button
              data-testid="delete-shootout-btn"
              class="px-3 py-1 text-[var(--color-error)] hover:bg-[var(--color-bg-base)] rounded"
              hx-delete="/fragments/shootouts/{{ shootout.id }}"
              hx-confirm="Delete this shootout?"
              hx-target="closest [data-testid='shootout-item']"
              hx-swap="outerHTML swap:0.3s"
            >
              Delete
            </button>
          </div>
        </div>
      {% endfor %}
    {% else %}
      <div class="text-center py-12">
        <p class="text-[var(--color-text-secondary)] text-lg mb-4">
          No shootouts yet
        </p>
        <p class="text-[var(--color-text-secondary)] text-sm">
          Create your first shootout to compare signal chains
        </p>
      </div>
    {% endif %}
  </div>
</div>
{% endblock %}
`;

  return new Response(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
}
