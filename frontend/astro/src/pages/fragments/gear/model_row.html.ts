/**
 * fragments/gear/model_row.html.ts - Outputs dist/fragments/gear/model_row.html
 *
 * Model row fragment for HTMX swap (toggle save state).
 * This is a Jinja2 fragment template.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `<!-- Model Row Fragment - STORY-005 -->
<!-- Returned by POST /api/v1/html/gear/model/{id}/toggle for HTMX swap -->
<div
  data-testid="model-row"
  data-model-id="{{ model.id }}"
  class="flex items-center justify-between px-4 py-3 bg-[var(--color-bg-elevated)] hover:bg-[var(--color-bg-secondary)] transition-colors"
>
  <div class="flex items-center gap-3 min-w-0">
    <!-- Model size badge -->
    {% if model.model_size %}
    <span class="flex-shrink-0 px-2 py-0.5 text-xs font-medium rounded bg-[var(--color-bg-secondary)] text-[var(--color-text-muted)]">
      {{ model.model_size | upper }}
    </span>
    {% endif %}
    <!-- Model name -->
    <span class="text-[var(--color-text-primary)] truncate" data-testid="model-name">
      {{ model.name }}
    </span>
    <!-- Download status -->
    <span class="flex-shrink-0 text-xs" data-testid="model-download-status">
      {% if model.download_status == 'completed' %}
      <span class="text-green-500">Downloaded</span>
      {% elif model.download_status == 'downloading' %}
      <span class="text-blue-400">Downloading</span>
      {% elif model.download_status == 'failed' %}
      <span class="text-red-400">Failed</span>
      {% else %}
      <span class="text-[var(--color-text-muted)]">Available</span>
      {% endif %}
    </span>
    <!-- Saved badge -->
    {% if model.is_saved %}
    <span class="flex-shrink-0 px-2 py-0.5 text-xs font-medium rounded bg-green-500/20 text-green-500" data-testid="saved-badge">
      Saved
    </span>
    {% endif %}
  </div>

  <!-- Save checkbox -->
  <div class="flex-shrink-0">
    <label class="flex items-center gap-2 cursor-pointer">
      <input
        type="checkbox"
        data-testid="model-save-checkbox"
        data-model-id="{{ model.id }}"
        {{ 'checked' if model.is_saved else '' }}
        hx-post="/api/v1/html/gear/model/{{ model.id }}/toggle"
        hx-swap="outerHTML"
        hx-target="closest [data-testid='model-row']"
        class="w-5 h-5 rounded border-[var(--border)] bg-[var(--color-bg-secondary)] text-[var(--color-accent-primary)] focus:ring-[var(--color-accent-primary)] focus:ring-offset-0"
      />
      <span class="text-sm text-[var(--color-text-muted)]">Save</span>
    </label>
  </div>
</div>
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
