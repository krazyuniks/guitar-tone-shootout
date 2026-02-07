/**
 * fragments/shootouts/create/step1-chains.html.ts - Outputs dist/fragments/shootouts/create/step1-chains.html
 *
 * Step 1 of shootout create wizard: Select Signal Chains.
 * Allows user to search and select 2+ signal chains from their library.
 * This is a Jinja2 fragment template.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `<!-- Step 1: Select Signal Chains -->
<div class="space-y-6" x-show="step === 1" x-transition>
  <!-- Step header -->
  <div class="flex items-center gap-3">
    <div class="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--color-accent-primary)] text-sm font-bold text-white">
      1
    </div>
    <h2 class="text-xl font-semibold">Select Signal Chains</h2>
  </div>

  <p class="text-[var(--color-text-secondary)]">
    Choose 2 or more signal chains from your library to compare.
  </p>

  <!-- Search -->
  <div class="relative">
    <div class="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        class="w-4 h-4"
      >
        <path
          fill-rule="evenodd"
          d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
          clip-rule="evenodd"
        />
      </svg>
    </div>
    <input
      type="text"
      placeholder="Search chains..."
      x-model="chainSearch"
      hx-get="/api/v1/html/shootout-create/chains"
      hx-trigger="keyup changed delay:300ms"
      hx-target="#chain-list-container"
      hx-include="[x-model='chainSearch']"
      class="w-full pl-10 rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      data-testid="chain-search-input"
    />
  </div>

  <!-- Selected count -->
  <div class="text-sm text-[var(--color-text-secondary)]">
    <span x-text="selectedChains.length"></span> selected
    <span x-show="selectedChains.length < 2">(minimum 2)</span>
  </div>

  <!-- Chain list container -->
  <div id="chain-list-container" hx-get="/api/v1/html/shootout-create/chains" hx-trigger="load" hx-swap="innerHTML">
    <!-- Loading skeleton -->
    <div class="space-y-2">
      <div class="h-16 bg-muted rounded-lg animate-pulse"></div>
      <div class="h-16 bg-muted rounded-lg animate-pulse"></div>
      <div class="h-16 bg-muted rounded-lg animate-pulse"></div>
      <div class="h-16 bg-muted rounded-lg animate-pulse"></div>
    </div>
  </div>

  <!-- Selected chips -->
  <div x-show="selectedChains.length > 0" class="flex flex-wrap gap-2">
    <template x-for="chain in selectedChains" :key="chain.id">
      <span class="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-[var(--color-accent-primary)]/20 text-[var(--color-accent-primary)]">
        <span x-text="chain.name"></span>
        <button
          type="button"
          @click="toggleChain(chain.id, chain.name, chain.block_count, chain.platform)"
          class="hover:opacity-70 transition-opacity"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            class="w-3 h-3"
          >
            <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
          </svg>
        </button>
      </span>
    </template>
  </div>

  <!-- Next button -->
  <div class="flex justify-end">
    <button
      type="button"
      @click="step = 2"
      :disabled="selectedChains.length < 2"
      :class="{
        'opacity-50 cursor-not-allowed': selectedChains.length < 2,
        'hover:opacity-90': selectedChains.length >= 2
      }"
      class="inline-flex items-center px-4 py-2 bg-[var(--color-accent-primary)] text-white rounded-md text-sm font-medium transition-opacity"
      data-testid="step1-next-btn"
    >
      Next: Select DI Track
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        class="w-4 h-4 ml-1"
      >
        <path
          fill-rule="evenodd"
          d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
          clip-rule="evenodd"
        />
      </svg>
    </button>
  </div>
</div>
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
