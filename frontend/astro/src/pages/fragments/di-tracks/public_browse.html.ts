/**
 * fragments/di-tracks/public_browse.html.ts - Outputs dist/fragments/di-tracks/public_browse.html
 *
 * Public DI Track Browse Results - displays public DI tracks for browsing.
 * Uses the shared track_item.html component with is_library_view=false.
 * This is a Jinja2 fragment template.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `<!-- Public DI Tracks Browse Results -->
<div data-testid="di-tracks-results" class="space-y-4">
  {% if tracks %}
    <!-- Results Header -->
    <div class="flex items-center justify-between mb-4">
      <p class="text-gray-400 text-sm">
        {{ total_count }} track{% if total_count != 1 %}s{% endif %} found
      </p>
    </div>

    <!-- Track List - uses shared track_item component -->
    <div class="space-y-3">
      {% for track in tracks %}
        {% with is_library_view=false %}
          {% include "fragments/library/track_item.html" %}
        {% endwith %}
      {% endfor %}
    </div>

    <!-- Pagination -->
    {% if total_count > tracks|length or offset > 0 %}
    <div class="flex items-center justify-center gap-2 mt-6">
      {% if prev_url %}
      <a
        href="{{ prev_url }}"
        data-testid="pagination-prev"
        hx-get="/api/v1/html{{ prev_url }}"
        hx-target="#di-tracks-results"
        hx-swap="innerHTML"
        class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
      >
        Previous
      </a>
      {% endif %}
      {% if next_url %}
      <a
        href="{{ next_url }}"
        data-testid="pagination-next"
        hx-get="/api/v1/html{{ next_url }}"
        hx-target="#di-tracks-results"
        hx-swap="innerHTML"
        class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
      >
        Next
      </a>
      {% endif %}
    </div>
    {% endif %}

  {% else %}
    <!-- Empty State -->
    <div class="text-center py-12">
      <svg xmlns="http://www.w3.org/2000/svg" class="mx-auto h-12 w-12 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
      </svg>
      <h3 class="mt-4 text-lg font-medium text-gray-300">No DI Tracks Found</h3>
      <p class="mt-2 text-gray-500">
        {% if search or tuning_filter %}
          Try adjusting your filters or search terms.
        {% else %}
          No public DI tracks are available yet.
        {% endif %}
      </p>
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
