/**
 * fragments/library/my_gear.html.ts - Outputs dist/fragments/library/my_gear.html
 *
 * My Gear Results Fragment (STORY-006) - displays user's saved gear with search,
 * gear type filters (All/Amps/Pedals/IRs/Full Rigs), results count, pack grid,
 * pagination, and empty states.
 * This is a Jinja2 fragment template.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `<!-- My Gear Results Fragment - STORY-006 -->
<div
  id="my-gear-results-container"
  data-testid="my-gear-results"
  data-empty="{{ 'true' if not packs else 'false' }}"
>
  <!-- Hidden state for HTMX includes -->
  <input type="hidden" name="page" value="{{ page }}" />
  <input type="hidden" name="page_size" value="{{ page_size }}" />

  <!-- Filters and Controls -->
  <div class="mb-6 space-y-4">
    <!-- Search bar -->
    <div class="relative">
      <div class="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
          <path fill-rule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clip-rule="evenodd"/>
        </svg>
      </div>
      <input
        type="text"
        name="search"
        placeholder="Search your gear..."
        value="{{ search or '' }}"
        class="w-full pl-10 pr-10 py-2 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--border)] text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent-primary)]"
        hx-get="/api/v1/html/my-gear/results?sort_by={{ sort_by }}&sort_order={{ sort_order }}&page=1&page_size={{ page_size }}"
        hx-trigger="keyup changed delay:300ms"
        hx-target="#my-gear-results-container"
        hx-swap="outerHTML"
        hx-include="[name='gear_type']"
      />
      {% if search %}
        <button
          type="button"
          class="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
          hx-get="/api/v1/html/my-gear/results?sort_by={{ sort_by }}&sort_order={{ sort_order }}&page=1&page_size={{ page_size }}"
          hx-target="#my-gear-results-container"
          hx-swap="outerHTML"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4">
            <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"/>
          </svg>
        </button>
      {% endif %}
    </div>

    <!-- Filter and Sort row -->
    <div class="flex flex-wrap items-center justify-between gap-3">
      <!-- Gear type filter buttons -->
      <div class="flex items-center gap-1.5">
      <!-- Gear type filter buttons -->
      <div class="flex items-center gap-1.5">
        <button
          name="gear_type"
          value=""
          data-testid="filter-gear-type-all"
          class="px-3 py-1.5 text-sm rounded-full border-2 transition-all {% if not gear_type_filter %}bg-[var(--color-accent-primary)] text-white border-transparent{% else %}bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] border-transparent hover:border-[var(--color-accent-primary)]{% endif %}"
          hx-get="/api/v1/html/my-gear/results?sort_by={{ sort_by }}&sort_order={{ sort_order }}&page=1&page_size={{ page_size }}"
          hx-target="#my-gear-results-container"
          hx-swap="outerHTML"
          hx-include="[name='search']"
        >
          All
        </button>
        <button
          name="gear_type"
          value="amp"
          data-testid="filter-gear-type-amp"
          class="px-3 py-1.5 text-sm rounded-full border-2 transition-all {% if gear_type_filter == 'amp' %}bg-orange-500 text-white border-transparent{% else %}bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] border-transparent hover:border-orange-500{% endif %}"
          hx-get="/api/v1/html/my-gear/results?gear_type=amp&sort_by={{ sort_by }}&sort_order={{ sort_order }}&page=1&page_size={{ page_size }}"
          hx-target="#my-gear-results-container"
          hx-swap="outerHTML"
          hx-include="[name='search']"
        >
          Amps
        </button>
        <button
          name="gear_type"
          value="pedal"
          data-testid="filter-gear-type-pedal"
          class="px-3 py-1.5 text-sm rounded-full border-2 transition-all {% if gear_type_filter == 'pedal' %}bg-purple-500 text-white border-transparent{% else %}bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] border-transparent hover:border-purple-500{% endif %}"
          hx-get="/api/v1/html/my-gear/results?gear_type=pedal&sort_by={{ sort_by }}&sort_order={{ sort_order }}&page=1&page_size={{ page_size }}"
          hx-target="#my-gear-results-container"
          hx-swap="outerHTML"
          hx-include="[name='search']"
        >
          Pedals
        </button>
        <button
          name="gear_type"
          value="ir"
          data-testid="filter-gear-type-ir"
          class="px-3 py-1.5 text-sm rounded-full border-2 transition-all {% if gear_type_filter == 'ir' %}bg-green-500 text-white border-transparent{% else %}bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] border-transparent hover:border-green-500{% endif %}"
          hx-get="/api/v1/html/my-gear/results?gear_type=ir&sort_by={{ sort_by }}&sort_order={{ sort_order }}&page=1&page_size={{ page_size }}"
          hx-target="#my-gear-results-container"
          hx-swap="outerHTML"
          hx-include="[name='search']"
        >
          IRs
        </button>
        <button
          name="gear_type"
          value="full-rig"
          data-testid="filter-gear-type-full-rig"
          class="px-3 py-1.5 text-sm rounded-full border-2 transition-all {% if gear_type_filter == 'full-rig' %}bg-yellow-400 text-black border-transparent{% else %}bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] border-transparent hover:border-yellow-400{% endif %}"
          hx-get="/api/v1/html/my-gear/results?gear_type=full-rig&sort_by={{ sort_by }}&sort_order={{ sort_order }}&page=1&page_size={{ page_size }}"
          hx-target="#my-gear-results-container"
          hx-swap="outerHTML"
          hx-include="[name='search']"
        >
          Full Rigs
        </button>
      </div>

      <!-- Sort control -->
      <div class="flex items-center gap-2" x-data="{ sortCombined: '{{ sort_by }}-{{ sort_order }}' }">
        <label class="text-sm text-[var(--color-text-secondary)]">Sort by:</label>
        <select
          data-testid="sort-select"
          class="px-3 py-1.5 text-sm rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--border)] text-[var(--color-text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent-primary)]"
          x-model="sortCombined"
          @change="() => {
            const [sortBy, sortOrder] = sortCombined.split('-');
            const searchVal = document.querySelector('[name=search]')?.value || '';
            const gearType = document.querySelector('[name=gear_type]:checked')?.value || '';
            const url = '/api/v1/html/my-gear/results?sort_by=' + sortBy + '&sort_order=' + sortOrder + '&page=1&page_size={{ page_size }}' + (searchVal ? '&search=' + encodeURIComponent(searchVal) : '') + (gearType ? '&gear_type=' + gearType : '');
            htmx.ajax('GET', url, { target: '#my-gear-results-container', swap: 'outerHTML' });
          }"
        >
          <option value="date_added-desc" {% if sort_by == 'date_added' and sort_order == 'desc' %}selected{% endif %}>Newest First</option>
          <option value="date_added-asc" {% if sort_by == 'date_added' and sort_order == 'asc' %}selected{% endif %}>Oldest First</option>
          <option value="name-asc" {% if sort_by == 'name' and sort_order == 'asc' %}selected{% endif %}>Name (A-Z)</option>
          <option value="name-desc" {% if sort_by == 'name' and sort_order == 'desc' %}selected{% endif %}>Name (Z-A)</option>
          <option value="type-asc" {% if sort_by == 'type' and sort_order == 'asc' %}selected{% endif %}>Type (A-Z)</option>
          <option value="type-desc" {% if sort_by == 'type' and sort_order == 'desc' %}selected{% endif %}>Type (Z-A)</option>
        </select>
      </div>
    </div>
  </div>

  <!-- Results count -->
  <div class="mb-4 text-sm text-[var(--color-text-secondary)]" data-testid="results-count">
    {{ total_models }} {{ 'model' if total_models == 1 else 'models' }} saved in {{ total_packs }} {{ 'pack' if total_packs == 1 else 'packs' }}
    {% if gear_type_filter or search %} (filtered){% endif %}
  </div>

  {% if packs %}
    <!-- Pack grid - 2 columns -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
      {% for pack in packs %}
        {% include 'fragments/library/my_gear_pack.html' %}
      {% endfor %}
    </div>

    <!-- Pagination -->
    {% if total_pages > 1 %}
    <div class="flex flex-col items-center gap-3 mt-8">
      <div class="text-sm text-[var(--color-text-secondary)]">
        Page {{ page }} of {{ total_pages }}
      </div>
      <div class="flex items-center gap-2" data-testid="pagination">
      <!-- First button -->
      <button
        data-testid="pagination-first"
        class="px-3 py-2 rounded-lg text-sm font-medium transition-colors {% if page > 1 %}bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface)]{% else %}bg-[var(--color-bg-secondary)] text-[var(--color-text-muted)] cursor-not-allowed{% endif %}"
        {% if page > 1 %}
        hx-get="/api/v1/html/my-gear/results?page=1&page_size={{ page_size }}&sort_by={{ sort_by }}&sort_order={{ sort_order }}{% if gear_type_filter %}&gear_type={{ gear_type_filter }}{% endif %}{% if search %}&search={{ search }}{% endif %}"
        hx-target="#my-gear-results-container"
        hx-swap="outerHTML"
        {% else %}
        disabled
        {% endif %}
      >
        First
      </button>

      <!-- Prev button -->
      <button
        data-testid="pagination-prev"
        class="px-3 py-2 rounded-lg text-sm font-medium transition-colors {% if has_prev %}bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface)]{% else %}bg-[var(--color-bg-secondary)] text-[var(--color-text-muted)] cursor-not-allowed{% endif %}"
        {% if has_prev %}
        hx-get="/api/v1/html/my-gear/results?page={{ page - 1 }}&page_size={{ page_size }}&sort_by={{ sort_by }}&sort_order={{ sort_order }}{% if gear_type_filter %}&gear_type={{ gear_type_filter }}{% endif %}{% if search %}&search={{ search }}{% endif %}"
        hx-target="#my-gear-results-container"
        hx-swap="outerHTML"
        {% else %}
        disabled
        {% endif %}
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
          <path fill-rule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clip-rule="evenodd"/>
        </svg>
      </button>

      <!-- Page numbers -->
      {% for page_num in range(1, total_pages + 1) %}
        <button
          data-testid="pagination-page-{{ page_num }}"
          class="px-3 py-2 rounded-lg text-sm font-medium transition-colors {% if page_num == page %}bg-[var(--color-accent-primary)] text-white{% else %}bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface)]{% endif %}"
          hx-get="/api/v1/html/my-gear/results?page={{ page_num }}&page_size={{ page_size }}&sort_by={{ sort_by }}&sort_order={{ sort_order }}{% if gear_type_filter %}&gear_type={{ gear_type_filter }}{% endif %}{% if search %}&search={{ search }}{% endif %}"
          hx-target="#my-gear-results-container"
          hx-swap="outerHTML"
        >
          {{ page_num }}
        </button>
      {% endfor %}

      <!-- Next button -->
      <button
        data-testid="pagination-next"
        class="px-3 py-2 rounded-lg text-sm font-medium transition-colors {% if has_next %}bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface)]{% else %}bg-[var(--color-bg-secondary)] text-[var(--color-text-muted)] cursor-not-allowed{% endif %}"
        {% if has_next %}
        hx-get="/api/v1/html/my-gear/results?page={{ page + 1 }}&page_size={{ page_size }}&sort_by={{ sort_by }}&sort_order={{ sort_order }}{% if gear_type_filter %}&gear_type={{ gear_type_filter }}{% endif %}{% if search %}&search={{ search }}{% endif %}"
        hx-target="#my-gear-results-container"
        hx-swap="outerHTML"
        {% else %}
        disabled
        {% endif %}
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
          <path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd"/>
        </svg>
      </button>

      <!-- Last button -->
      <button
        data-testid="pagination-last"
        class="px-3 py-2 rounded-lg text-sm font-medium transition-colors {% if page < total_pages %}bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface)]{% else %}bg-[var(--color-bg-secondary)] text-[var(--color-text-muted)] cursor-not-allowed{% endif %}"
        {% if page < total_pages %}
        hx-get="/api/v1/html/my-gear/results?page={{ total_pages }}&page_size={{ page_size }}&sort_by={{ sort_by }}&sort_order={{ sort_order }}{% if gear_type_filter %}&gear_type={{ gear_type_filter }}{% endif %}{% if search %}&search={{ search }}{% endif %}"
        hx-target="#my-gear-results-container"
        hx-swap="outerHTML"
        {% else %}
        disabled
        {% endif %}
      >
        Last
      </button>
      </div>
    </div>
    {% endif %}
  {% else %}
    <!-- Empty state -->
    <div class="text-center py-12" data-testid="my-gear-empty">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-12 h-12 mx-auto text-[var(--color-block-amp)] mb-4">
        <path d="M19.952 1.651a.75.75 0 01.298.599V16.303a3 3 0 01-2.176 2.884l-1.32.377a2.553 2.553 0 11-1.403-4.909l2.311-.66a1.5 1.5 0 001.088-1.442V6.994l-9 2.572v9.737a3 3 0 01-2.176 2.884l-1.32.377a2.553 2.553 0 11-1.402-4.909l2.31-.66a1.5 1.5 0 001.088-1.442V5.25a.75.75 0 01.544-.721l10.5-3a.75.75 0 01.658.122z"/>
      </svg>
      <h2 class="text-xl font-semibold text-[var(--color-text-primary)] mb-2">
        {% if gear_type_filter or search %}
          No gear matches your filters
        {% else %}
          No Saved Gear Yet
        {% endif %}
      </h2>
      <p class="text-[var(--color-text-secondary)] mb-6 max-w-md mx-auto">
        {% if gear_type_filter or search %}
          Try adjusting your search or filters to find what you're looking for.
        {% else %}
          Start building your gear library by browsing Tone 3000 packs and saving models.
        {% endif %}
      </p>
      {% if gear_type_filter or search %}
        <button
          class="px-4 py-2 rounded-lg border border-[var(--border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-elevated)] transition-colors"
          hx-get="/api/v1/html/my-gear/results?sort_by={{ sort_by }}&sort_order={{ sort_order }}&page=1&page_size={{ page_size }}"
          hx-target="#my-gear-results-container"
          hx-swap="outerHTML"
        >
          Clear Filters
        </button>
      {% else %}
        <a
          href="/gear"
          class="inline-flex items-center px-4 py-2 rounded-lg bg-[var(--color-accent-primary)] text-white hover:bg-[var(--color-accent-secondary)] transition-colors"
        >
          Browse More Gear
        </a>
      {% endif %}
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
