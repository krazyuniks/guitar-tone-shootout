/**
 * pages/library/shootouts.html.ts - Outputs dist/pages/library/shootouts.html
 *
 * My Shootouts library page.
 * This is a Jinja2 template for the SSR page.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `{% extends "layouts/base.html" %}

{% block title %}My Shootouts - Guitar Tone Shootout{% endblock %}
{% block description %}View and manage your tone comparison shootouts.{% endblock %}

{% block content %}
<div
  data-testid="shootouts-library"
  class="container mx-auto px-4 py-8"
>
  <!-- Header -->
  <div class="mb-8">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-[var(--color-text-primary)] mb-2">
          My Shootouts
        </h1>
        <p class="text-[var(--color-text-secondary)]">
          View and manage your tone comparison shootouts
        </p>
      </div>
      <a
        href="/shootout/create"
        class="inline-flex items-center gap-2 px-4 py-2 bg-[var(--color-accent-primary)] hover:bg-[var(--color-accent-primary-hover)] text-white font-medium rounded-lg transition-colors"
        data-testid="create-shootout-btn"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
          <path d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z" />
        </svg>
        Create Shootout
      </a>
    </div>
  </div>

  <!-- HTMX-powered shootouts list -->
  <div
    id="shootouts-list-container"
    data-testid="shootouts-list-container"
    hx-get="/api/v1/html/library/shootouts"
    hx-trigger="load"
    hx-swap="innerHTML"
  >
    <!-- Loading state while HTMX fetches content -->
    <div class="space-y-4">
      {% for i in range(4) %}
      <div class="bg-[var(--color-bg-elevated)] rounded-lg p-4 animate-pulse">
        <div class="flex items-start gap-4">
          <div class="flex-shrink-0 w-24 h-24 bg-[var(--color-bg-secondary)] rounded-lg"></div>
          <div class="flex-1">
            <div class="h-5 bg-[var(--color-bg-secondary)] rounded w-3/4 mb-2"></div>
            <div class="h-4 bg-[var(--color-bg-secondary)] rounded w-1/2 mb-2"></div>
            <div class="flex gap-2">
              <div class="h-4 w-16 bg-[var(--color-bg-secondary)] rounded"></div>
              <div class="h-4 w-24 bg-[var(--color-bg-secondary)] rounded"></div>
            </div>
          </div>
        </div>
      </div>
      {% endfor %}
    </div>
  </div>
</div>
{% endblock %}

{% block scripts %}
<script>
  // Handle HTMX response errors for auth
  document.body.addEventListener('htmx:responseError', (event) => {
    const xhr = event.detail?.xhr;
    if (xhr && xhr.status === 401) {
      // Not authenticated - redirect to login
      const currentPath = window.location.pathname;
      window.location.href = \`/login?next=\${encodeURIComponent(currentPath)}\`;
    }
  });
</script>
{% endblock %}
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
