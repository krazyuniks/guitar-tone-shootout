/**
 * fragments/gear/public_browse.html.ts - Outputs dist/fragments/gear/public_browse.html
 *
 * Public gear browse fragment with filters and pack cards.
 * Pure SSR — standard forms and links, no HTMX.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `<!-- Public Gear Browse Fragment — SSR with standard forms/links -->
<div id="gear-results-container" data-testid="gear-results" data-empty="{{ 'true' if not packs else 'false' }}">

  <!-- Filters -->
  <div class="mb-6 space-y-4">
    <!-- Search bar (standard form) -->
    <form method="get" action="/gear" data-testid="gear-search-form" class="flex items-center gap-2">
      <!-- Preserve current filters -->
      <input type="hidden" name="gear_type" value="{{ gear_type_filter }}">
      <input type="hidden" name="sort" value="{{ sort_order }}">
      {% if tags_filter %}<input type="hidden" name="tags" value="{{ tags_filter|join(',') }}">{% endif %}

      <div class="relative max-w-md flex-1">
        <div class="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path fill-rule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clip-rule="evenodd"/>
          </svg>
        </div>
        <input
          type="text"
          name="search"
          placeholder="Search gear packs..."
          value="{{ search or '' }}"
          autocomplete="off"
          data-testid="search-input"
          class="w-full pl-10 pr-10 py-2 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--border)] text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent-primary)]"
        />
        {% if search %}
          <a
            href="/gear{% if gear_type_filter %}?gear_type={{ gear_type_filter }}&sort={{ sort_order }}{% elif sort_order != 'newest' %}?sort={{ sort_order }}{% endif %}"
            data-testid="clear-search-button"
            class="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"/>
            </svg>
          </a>
        {% endif %}
      </div>
      <button
        type="submit"
        data-testid="search-button"
        class="px-4 py-2 rounded-lg text-sm font-medium bg-[var(--color-accent-primary)] text-white hover:opacity-90 transition-opacity"
      >
        Search
      </button>
    </form>

    <!-- Filter row -->
    <div class="flex flex-wrap items-center gap-3">
      <!-- Gear type filter links -->
      <div class="flex items-center gap-1.5">
        <a
          href="/gear?sort={{ sort_order }}{% if search %}&search={{ search|urlencode }}{% endif %}"
          data-testid="filter-all"
          class="px-3 py-1.5 text-sm rounded-full border-2 transition-all {% if not gear_type_filter %}bg-[var(--color-accent-primary)] text-white border-transparent active-filter{% else %}bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] border-transparent{% endif %}"
        >
          All
        </a>
        <a
          href="/gear?gear_type=amp&sort={{ sort_order }}{% if search %}&search={{ search|urlencode }}{% endif %}"
          data-testid="filter-amp"
          class="px-3 py-1.5 text-sm rounded-full border-2 transition-all {% if gear_type_filter == 'amp' %}bg-orange-500 text-white border-transparent active-filter{% else %}bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] border-transparent{% endif %}"
        >
          Amps
        </a>
        <a
          href="/gear?gear_type=pedal&sort={{ sort_order }}{% if search %}&search={{ search|urlencode }}{% endif %}"
          data-testid="filter-pedal"
          class="px-3 py-1.5 text-sm rounded-full border-2 transition-all {% if gear_type_filter == 'pedal' %}bg-purple-500 text-white border-transparent active-filter{% else %}bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] border-transparent{% endif %}"
        >
          Pedals
        </a>
        <a
          href="/gear?gear_type=ir&sort={{ sort_order }}{% if search %}&search={{ search|urlencode }}{% endif %}"
          data-testid="filter-ir"
          class="px-3 py-1.5 text-sm rounded-full border-2 transition-all {% if gear_type_filter == 'ir' %}bg-green-500 text-white border-transparent active-filter{% else %}bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] border-transparent{% endif %}"
        >
          IRs
        </a>
        <a
          href="/gear?gear_type=full-rig&sort={{ sort_order }}{% if search %}&search={{ search|urlencode }}{% endif %}"
          data-testid="filter-full-rig"
          class="px-3 py-1.5 text-sm rounded-full border-2 transition-all {% if gear_type_filter == 'full-rig' %}bg-yellow-400 text-black border-transparent active-filter{% else %}bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] border-transparent{% endif %}"
        >
          Full Rigs
        </a>
      </div>

      <!-- Spacer -->
      <div class="flex-1"></div>

      <!-- Sort dropdown (standard form) -->
      <form method="get" action="/gear" data-testid="gear-sort-form">
        <input type="hidden" name="search" value="{{ search }}">
        <input type="hidden" name="gear_type" value="{{ gear_type_filter }}">
        {% if tags_filter %}<input type="hidden" name="tags" value="{{ tags_filter|join(',') }}">{% endif %}
        <select
          name="sort"
          data-testid="filter-sort-dropdown"
          class="px-3 py-1.5 text-sm rounded-lg bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] border border-[var(--border)] focus:ring-1 focus:ring-[var(--color-accent-primary)]"
          onchange="this.form.submit()"
        >
          {% if search %}
          <option value="best-match" {% if sort_order == 'best-match' %}selected{% endif %}>Best Match</option>
          {% endif %}
          <option value="newest" {% if sort_order == 'newest' or (not sort_order and not search) %}selected{% endif %}>Newest</option>
          <option value="oldest" {% if sort_order == 'oldest' %}selected{% endif %}>Oldest</option>
          <option value="downloads" {% if sort_order == 'downloads' %}selected{% endif %}>Most Downloaded</option>
          <option value="favorites" {% if sort_order == 'favorites' %}selected{% endif %}>Most Favorited</option>
          <option value="trending" {% if sort_order == 'trending' %}selected{% endif %}>Trending</option>
        </select>
      </form>
    </div>
  </div>

  <!-- Results container -->
  <div id="gear-results">
    <!-- Results count -->
    <div class="mb-4 text-sm text-[var(--color-text-secondary)]" data-testid="results-count">
      {{ total_count }} {{ 'pack' if total_count == 1 else 'packs' }} available
      {% if gear_type_filter or search or tags_filter or makes_filter or creator_filter %} (filtered){% endif %}
    </div>

    {% if packs %}
    <!-- Pack grid -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
      {% for pack in packs %}
        {% include 'fragments/gear/public_pack_card.html' %}
      {% endfor %}
    </div>

    <!-- Pagination with standard links -->
    {% if total_pages > 1 %}
    <div class="flex items-center justify-center gap-2 mt-8" data-testid="pagination">
      {% if has_prev %}
        <a
          href="{{ prev_url }}"
          data-testid="pagination-prev"
          class="px-3 py-2 rounded-lg text-sm font-medium transition-colors bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface)]"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path fill-rule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clip-rule="evenodd"/>
          </svg>
        </a>
      {% else %}
        <button
          disabled
          class="px-3 py-2 rounded-lg text-sm font-medium bg-[var(--color-bg-secondary)] text-[var(--color-text-muted)] cursor-not-allowed"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path fill-rule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clip-rule="evenodd"/>
          </svg>
        </button>
      {% endif %}

      <span class="px-4 py-2 text-sm text-[var(--color-text-secondary)]" data-testid="pagination-info">
        Page {{ page }} of {{ total_pages }}
      </span>

      {% if has_next %}
        <a
          href="{{ next_url }}"
          data-testid="pagination-next"
          class="px-3 py-2 rounded-lg text-sm font-medium transition-colors bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-surface)]"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd"/>
          </svg>
        </a>
      {% else %}
        <button
          disabled
          class="px-3 py-2 rounded-lg text-sm font-medium bg-[var(--color-bg-secondary)] text-[var(--color-text-muted)] cursor-not-allowed"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd"/>
          </svg>
        </button>
      {% endif %}
    </div>
    {% endif %}
  {% else %}
    <!-- Empty state -->
    <div class="text-center py-12" data-testid="empty-state">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-12 h-12 mx-auto text-[var(--color-block-amp)] mb-4">
        <path d="M19.952 1.651a.75.75 0 01.298.599V16.303a3 3 0 01-2.176 2.884l-1.32.377a2.553 2.553 0 11-1.403-4.909l2.311-.66a1.5 1.5 0 001.088-1.442V6.994l-9 2.572v9.737a3 3 0 01-2.176 2.884l-1.32.377a2.553 2.553 0 11-1.402-4.909l2.31-.66a1.5 1.5 0 001.088-1.442V5.25a.75.75 0 01.544-.721l10.5-3a.75.75 0 01.658.122z"/>
      </svg>
      <h2 class="text-xl font-semibold text-[var(--color-text-primary)] mb-2">
        {% if gear_type_filter or search or tags_filter or makes_filter or creator_filter %}
          No packs match your filters
        {% else %}
          No Gear Packs Available
        {% endif %}
      </h2>
      <p class="text-[var(--color-text-secondary)] mb-6 max-w-md mx-auto">
        {% if gear_type_filter or search or tags_filter or makes_filter or creator_filter %}
          Try adjusting your search or filters to find what you're looking for.
        {% else %}
          Check back later for new gear packs from Tone3000.
        {% endif %}
      </p>
      {% if gear_type_filter or search or tags_filter or makes_filter or creator_filter %}
        <a
          href="/gear"
          data-testid="empty-state-clear-filters"
          class="px-4 py-2 rounded-lg border border-[var(--border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-elevated)] transition-colors"
        >
          Clear Filters
        </a>
      {% endif %}
    </div>
  {% endif %}
  </div><!-- end gear-results -->
</div>

<style>
/* Hover border colors for inactive filter buttons */
[data-testid^="filter-"][data-testid$="-all"]:not(.active-filter):hover,
[data-testid="filter-amp"]:not(.active-filter):hover,
[data-testid="filter-pedal"]:not(.active-filter):hover,
[data-testid="filter-ir"]:not(.active-filter):hover,
[data-testid="filter-full-rig"]:not(.active-filter):hover {
  border-color: var(--hover-color) !important;
}
[data-testid="filter-all"]:not(.active-filter) { --hover-color: var(--color-accent-primary); }
[data-testid="filter-amp"]:not(.active-filter) { --hover-color: #f59e0b; }
[data-testid="filter-pedal"]:not(.active-filter) { --hover-color: #a855f7; }
[data-testid="filter-ir"]:not(.active-filter) { --hover-color: #22c55e; }
[data-testid="filter-full-rig"]:not(.active-filter) { --hover-color: #facc15; }
</style>
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
