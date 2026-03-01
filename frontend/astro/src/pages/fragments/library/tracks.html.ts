/**
 * fragments/library/tracks.html.ts - Outputs dist/fragments/library/tracks.html
 *
 * Library DI Tracks List Fragment - displays a list of DI tracks
 * or an empty state encouraging users to upload raw guitar recordings.
 * This is a Jinja2 fragment template.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `<!-- Library DI Tracks List Fragment -->
<div data-testid="track-list" data-empty="{{ 'true' if not tracks else 'false' }}">
  <!-- Sort control -->
  <div class="mb-4 flex items-center justify-between">
    <div class="text-sm text-[var(--color-text-secondary)]">
      {{ total_count }} {{ 'track' if total_count == 1 else 'tracks' }}
    </div>
    <div class="flex items-center gap-2" x-data="{ sortCombined: '{{ sort_by }}-{{ sort_order }}' }">
      <label class="text-sm text-[var(--color-text-secondary)]">Sort by:</label>
      <select
        data-testid="sort-select"
        class="px-3 py-1.5 text-sm rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--border)] text-[var(--color-text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent-primary)]"
        x-model="sortCombined"
        @change="() => {
          const [sortBy, sortOrder] = sortCombined.split('-');
          window.location.href = '/library/di-tracks?sort_by=' + sortBy + '&sort_order=' + sortOrder + '&page=1&page_size={{ page_size }}';
        }"
      >
        <option value="date_added-desc" {% if sort_by == 'date_added' and sort_order == 'desc' %}selected{% endif %}>Newest First</option>
        <option value="date_added-asc" {% if sort_by == 'date_added' and sort_order == 'asc' %}selected{% endif %}>Oldest First</option>
        <option value="name-asc" {% if sort_by == 'name' and sort_order == 'asc' %}selected{% endif %}>Name (A-Z)</option>
        <option value="name-desc" {% if sort_by == 'name' and sort_order == 'desc' %}selected{% endif %}>Name (Z-A)</option>
      </select>
    </div>
  </div>

  {% if tracks %}
    <!-- Track items -->
    <div class="space-y-3">
      {% for track in tracks %}
        {% with is_library_view=true %}
          {% include 'fragments/library/track_item.html' %}
        {% endwith %}
      {% endfor %}
    </div>

    <!-- Pagination -->
    {% if total_pages > 1 %}
    <div class="flex items-center justify-center gap-2 mt-8" data-testid="pagination">
      {% if page > 1 %}
        <a href="/library/di-tracks?page=1&page_size={{ page_size }}&sort_by={{ sort_by }}&sort_order={{ sort_order }}" data-testid="pagination-first" class="px-3 py-2 rounded-lg text-sm font-medium transition-colors bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface)]">First</a>
        <a href="/library/di-tracks?page={{ page - 1 }}&page_size={{ page_size }}&sort_by={{ sort_by }}&sort_order={{ sort_order }}" data-testid="pagination-prev" class="px-3 py-2 rounded-lg text-sm font-medium transition-colors bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface)]">Prev</a>
      {% else %}
        <span data-testid="pagination-first" class="px-3 py-2 rounded-lg text-sm font-medium bg-[var(--color-bg-secondary)] text-[var(--color-text-muted)] cursor-not-allowed">First</span>
        <span data-testid="pagination-prev" class="px-3 py-2 rounded-lg text-sm font-medium bg-[var(--color-bg-secondary)] text-[var(--color-text-muted)] cursor-not-allowed">Prev</span>
      {% endif %}

      {% for page_num in range(1, total_pages + 1) %}
        {% if page_num == page %}
          <span data-testid="pagination-page-{{ page_num }}" class="px-3 py-2 rounded-lg text-sm font-medium bg-[var(--color-accent-primary)] text-white">{{ page_num }}</span>
        {% else %}
          <a href="/library/di-tracks?page={{ page_num }}&page_size={{ page_size }}&sort_by={{ sort_by }}&sort_order={{ sort_order }}" data-testid="pagination-page-{{ page_num }}" class="px-3 py-2 rounded-lg text-sm font-medium transition-colors bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface)]">{{ page_num }}</a>
        {% endif %}
      {% endfor %}

      {% if has_next %}
        <a href="/library/di-tracks?page={{ page + 1 }}&page_size={{ page_size }}&sort_by={{ sort_by }}&sort_order={{ sort_order }}" data-testid="pagination-next" class="px-3 py-2 rounded-lg text-sm font-medium transition-colors bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface)]">Next</a>
        <a href="/library/di-tracks?page={{ total_pages }}&page_size={{ page_size }}&sort_by={{ sort_by }}&sort_order={{ sort_order }}" data-testid="pagination-last" class="px-3 py-2 rounded-lg text-sm font-medium transition-colors bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface)]">Last</a>
      {% else %}
        <span data-testid="pagination-next" class="px-3 py-2 rounded-lg text-sm font-medium bg-[var(--color-bg-secondary)] text-[var(--color-text-muted)] cursor-not-allowed">Next</span>
        <span data-testid="pagination-last" class="px-3 py-2 rounded-lg text-sm font-medium bg-[var(--color-bg-secondary)] text-[var(--color-text-muted)] cursor-not-allowed">Last</span>
      {% endif %}
    </div>
    {% endif %}
  {% else %}
    <!-- Empty state -->
    <div class="text-center py-12">
      <div class="text-gray-400 mb-2">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
        </svg>
      </div>
      <p class="text-gray-500">No DI tracks yet</p>
      <p class="text-gray-400 text-sm mt-1">Upload your raw guitar recordings to use in shootouts</p>
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
