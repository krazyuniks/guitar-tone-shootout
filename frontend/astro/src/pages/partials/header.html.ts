/**
 * partials/header.html.ts - Outputs dist/partials/header.html
 *
 * Header partial with navigation and auth state.
 * This is a Jinja2 partial template included by other templates.
 *
 * Route rename: /browse → /shootouts (Issue #515)
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `{# Header partial with navigation and auth state #}
{# Variables: user (optional User object from context), current_path (optional) #}
{# STORY-006: Redesigned navigation - no dropdowns, centered nav, increased height #}
{# Design reference: JHS Pedals style - clean, prominent navigation #}

{% set current_path = request.url.path if request else '' %}

<header
  class="sticky top-0 z-50 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
  {% if user %}data-user-id="{{ user.id }}"{% if ws_token %} data-ws-token="{{ ws_token }}"{% endif %}{% endif %}
  x-data="{ mobileMenuOpen: false }"
>
  <nav class="container mx-auto flex h-20 items-center px-4">
    <!-- Logo - Left aligned, hx-boost=false for full page navigation to Astro home page -->
    <a href="/" hx-boost="false" class="flex items-center gap-2 text-xl font-bold shrink-0">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
           class="h-7 w-7 text-amber-500" aria-hidden="true">
        <path d="m11.9 12.1 4.514-4.514" />
        <path d="M20.1 2.3a1 1 0 0 0-1.4 0l-1.114 1.114A2 2 0 0 0 17 4.828v1.344a2 2 0 0 1-.586 1.414A2 2 0 0 1 17.828 7h1.344a2 2 0 0 0 1.414-.586L21.7 5.3a1 1 0 0 0 0-1.4z" />
        <path d="m6 16 2 2" />
        <path d="M8.2 9.9C8.7 8.8 9.8 8 11 8c2.8 0 5 2.2 5 5 0 1.2-.8 2.3-1.9 2.8l-.9.4A2 2 0 0 0 12 18a4 4 0 0 1-4 4c-3.3 0-6-2.7-6-6a4 4 0 0 1 4-4 2 2 0 0 0 1.8-1.2z" />
        <path d="m6 12 2-2" />
      </svg>
      <span class="text-amber-500">Tone Shootout</span>
    </a>

    <!-- Central Navigation - Desktop -->
    <div class="hidden md:flex flex-1 justify-center" data-testid="nav-main-links">
      <div class="flex items-center gap-1">
        <!-- Browse: Shootouts -->
        <a
          href="/shootouts"

          class="px-4 py-2 text-sm font-medium rounded-lg transition-colors {% if current_path == '/shootouts' %}text-amber-400 bg-amber-400/10{% else %}text-[var(--color-text-secondary)] hover:text-amber-400 hover:bg-amber-400/10{% endif %}"
          data-testid="nav-shootouts"
        >
          Shootouts
        </a>

        <!-- Browse: Gear -->
        <a
          href="/gear"

          class="px-4 py-2 text-sm font-medium rounded-lg transition-colors {% if current_path.startswith('/gear') %}text-amber-400 bg-amber-400/10{% else %}text-[var(--color-text-secondary)] hover:text-amber-400 hover:bg-amber-400/10{% endif %}"
          data-testid="nav-gear"
        >
          Gear
        </a>

        <!-- Browse: DI Tracks -->
        <a
          href="/di-tracks"

          class="px-4 py-2 text-sm font-medium rounded-lg transition-colors {% if current_path.startswith('/di-tracks') %}text-amber-400 bg-amber-400/10{% else %}text-[var(--color-text-secondary)] hover:text-amber-400 hover:bg-amber-400/10{% endif %}"
          data-testid="nav-di-tracks"
        >
          DI Tracks
        </a>

        {% if user %}
          <!-- Divider -->
          <span class="mx-2 h-6 w-px bg-border"></span>

          <!-- Library Links -->
          <a
            href="/library/my-gear"

            class="px-4 py-2 text-sm font-medium rounded-lg transition-colors {% if current_path == '/library/my-gear' %}text-amber-400 bg-amber-400/10{% else %}text-[var(--color-text-secondary)] hover:text-amber-400 hover:bg-amber-400/10{% endif %}"
            data-testid="nav-my-gear"
          >
            My Gear
          </a>
          <a
            href="/library/di-tracks"

            class="px-4 py-2 text-sm font-medium rounded-lg transition-colors {% if current_path == '/library/di-tracks' %}text-amber-400 bg-amber-400/10{% else %}text-[var(--color-text-secondary)] hover:text-amber-400 hover:bg-amber-400/10{% endif %}"
            data-testid="nav-my-di-tracks"
          >
            My DI Tracks
          </a>
          <a
            href="/library/chains"

            class="px-4 py-2 text-sm font-medium rounded-lg transition-colors {% if current_path == '/library/chains' %}text-amber-400 bg-amber-400/10{% else %}text-[var(--color-text-secondary)] hover:text-amber-400 hover:bg-amber-400/10{% endif %}"
            data-testid="nav-my-chains"
          >
            Chains
          </a>
          <a
            href="/library/shootouts"

            class="px-4 py-2 text-sm font-medium rounded-lg transition-colors {% if current_path == '/library/shootouts' %}text-amber-400 bg-amber-400/10{% else %}text-[var(--color-text-secondary)] hover:text-amber-400 hover:bg-amber-400/10{% endif %}"
            data-testid="nav-my-shootouts"
          >
            My Shootouts
          </a>

          <!-- Divider -->
          <span class="mx-2 h-6 w-px bg-border"></span>

          <!-- Create Shootout -->
          <a
            href="/shootout/create"

            class="px-4 py-2 text-sm font-medium rounded-lg transition-colors {% if current_path == '/shootout/create' %}text-amber-400 bg-amber-500/20{% else %}bg-amber-500/10 text-amber-400 hover:bg-amber-500/20{% endif %}"
            data-testid="nav-create-shootout"
          >
            Create
          </a>
        {% endif %}
      </div>
    </div>

    <!-- Right side - Auth -->
    <div class="hidden md:flex items-center gap-4 shrink-0">
      {% if user %}
        <span class="text-sm text-[var(--color-text-muted)]">{{ user.username }}</span>
        <button
          type="button"
          hx-post="/api/v1/auth/logout"
          hx-swap="none"
          hx-on::after-request="window.location.href = '/'"
          class="text-sm text-[var(--color-text-muted)] hover:text-amber-400 transition-colors"
          data-testid="nav-logout"
        >
          Logout
        </button>
      {% else %}
        <!-- Login Link - hx-boost=false for cross-origin navigation -->
        <a
          href="/login"
          hx-boost="false"
          class="px-4 py-2 text-sm font-medium rounded-lg text-[var(--color-text-secondary)] hover:text-amber-400 hover:bg-amber-400/10 transition-colors"
          data-testid="nav-login"
        >
          Login
        </a>
      {% endif %}
    </div>

    <!-- Mobile Menu Button -->
    <button
      type="button"
      class="inline-flex items-center justify-center rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground md:hidden ml-auto"
      aria-label="Toggle menu"
      @click="mobileMenuOpen = !mobileMenuOpen"
      data-testid="nav-mobile-toggle"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24"
           stroke="currentColor" stroke-width="2" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
      </svg>
    </button>
  </nav>

  <!-- Mobile Navigation -->
  <div
    class="border-t border-border md:hidden bg-background"
    x-show="mobileMenuOpen"
    x-transition:enter="transition ease-out duration-200"
    x-transition:enter-start="opacity-0 -translate-y-1"
    x-transition:enter-end="opacity-100 translate-y-0"
    x-transition:leave="transition ease-in duration-150"
    x-transition:leave-start="opacity-100 translate-y-0"
    x-transition:leave-end="opacity-0 -translate-y-1"
    x-cloak
  >
    <div class="px-4 py-4 space-y-1">
      <!-- Browse Links (visible to all) -->
      <a
        href="/shootouts"

        class="block rounded-lg px-4 py-3 text-base font-medium transition-colors {% if current_path == '/shootouts' %}text-amber-400 bg-amber-400/10{% else %}text-[var(--color-text-secondary)] hover:bg-amber-400/10 hover:text-amber-400{% endif %}"
        data-testid="nav-mobile-shootouts"
      >
        Shootouts
      </a>
      <a
        href="/gear"

        class="block rounded-lg px-4 py-3 text-base font-medium transition-colors {% if current_path.startswith('/gear') %}text-amber-400 bg-amber-400/10{% else %}text-[var(--color-text-secondary)] hover:bg-amber-400/10 hover:text-amber-400{% endif %}"
        data-testid="nav-mobile-gear"
      >
        Gear
      </a>
      <a
        href="/di-tracks"

        class="block rounded-lg px-4 py-3 text-base font-medium transition-colors {% if current_path.startswith('/di-tracks') %}text-amber-400 bg-amber-400/10{% else %}text-[var(--color-text-secondary)] hover:bg-amber-400/10 hover:text-amber-400{% endif %}"
        data-testid="nav-mobile-di-tracks"
      >
        DI Tracks
      </a>

      {% if user %}
        <!-- Library Links -->
        <div class="border-t border-border pt-4 mt-4 space-y-1">
          <a
            href="/library/my-gear"

            class="block rounded-lg px-4 py-3 text-base font-medium transition-colors {% if current_path == '/library/my-gear' %}text-amber-400 bg-amber-400/10{% else %}text-[var(--color-text-secondary)] hover:bg-amber-400/10 hover:text-amber-400{% endif %}"
            data-testid="nav-mobile-my-gear"
          >
            My Gear
          </a>
          <a
            href="/library/di-tracks"

            class="block rounded-lg px-4 py-3 text-base font-medium transition-colors {% if current_path == '/library/di-tracks' %}text-amber-400 bg-amber-400/10{% else %}text-[var(--color-text-secondary)] hover:bg-amber-400/10 hover:text-amber-400{% endif %}"
            data-testid="nav-mobile-my-di-tracks"
          >
            My DI Tracks
          </a>
          <a
            href="/library/chains"

            class="block rounded-lg px-4 py-3 text-base font-medium transition-colors {% if current_path == '/library/chains' %}text-amber-400 bg-amber-400/10{% else %}text-[var(--color-text-secondary)] hover:bg-amber-400/10 hover:text-amber-400{% endif %}"
            data-testid="nav-mobile-my-chains"
          >
            Chains
          </a>
          <a
            href="/library/shootouts"

            class="block rounded-lg px-4 py-3 text-base font-medium transition-colors {% if current_path == '/library/shootouts' %}text-amber-400 bg-amber-400/10{% else %}text-[var(--color-text-secondary)] hover:bg-amber-400/10 hover:text-amber-400{% endif %}"
            data-testid="nav-mobile-my-shootouts"
          >
            My Shootouts
          </a>

          <!-- Create Shootout -->
          <a
            href="/shootout/create"

            class="block rounded-lg px-4 py-3 text-base font-medium transition-colors {% if current_path == '/shootout/create' %}text-amber-400 bg-amber-500/20{% else %}bg-amber-500/10 text-amber-400 hover:bg-amber-500/20{% endif %}"
            data-testid="nav-mobile-create-shootout"
          >
            Create Shootout
          </a>
        </div>

        <!-- User Section -->
        <div class="border-t border-border pt-4 mt-4 px-4">
          <span class="block py-2 text-sm text-[var(--color-text-muted)]">{{ user.username }}</span>
          <button
            type="button"
            hx-post="/api/v1/auth/logout"
            hx-swap="none"
            hx-on::after-request="window.location.href = '/'"
            class="block w-full text-left py-2 text-base font-medium text-[var(--color-text-muted)] hover:text-amber-400"
            data-testid="nav-mobile-logout"
          >
            Logout
          </button>
        </div>
      {% else %}
        <!-- Login (unauthenticated) - hx-boost=false for cross-origin navigation -->
        <div class="border-t border-border pt-4 mt-4">
          <a
            href="/login"
            hx-boost="false"
            class="block rounded-lg px-4 py-3 text-base font-medium text-[var(--color-text-secondary)] hover:bg-amber-400/10 hover:text-amber-400"
            data-testid="nav-mobile-login"
          >
            Login
          </a>
        </div>
      {% endif %}
    </div>
  </div>
</header>

<style>
  [x-cloak] { display: none !important; }
</style>
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
