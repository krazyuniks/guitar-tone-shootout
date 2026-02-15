/**
 * pages/shootouts.html.ts - Outputs dist/pages/shootouts.html
 *
 * Browse shootouts page (renamed from /browse to /shootouts per Issue #515).
 * This is a Jinja2 template for the SSR page.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `{% extends "layouts/base.html" %}

{% block title %}Shootouts{% endblock %}

{% block content %}
<div data-testid="shootouts-page" class="min-h-screen">
  {# HTMX container that loads sections on page load #}
  <div
    id="shootouts-sections-container"
    data-testid="shootouts-sections-container"
    hx-get="/api/v1/html/shootouts/sections"
    hx-trigger="load"
    hx-swap="innerHTML"
  >
    {# Loading state - shows until HTMX replaces content #}
    <div class="container mx-auto px-4">
      {# Hero skeleton #}
      <div class="text-center py-12 px-4">
        <div class="h-10 w-72 mx-auto bg-[var(--color-bg-elevated)] rounded animate-pulse mb-4"></div>
        <div class="h-6 w-96 mx-auto bg-[var(--color-bg-elevated)] rounded animate-pulse"></div>
      </div>

      {# Section skeletons #}
      <div class="space-y-8 pb-12">
        {# Trending section skeleton #}
        <div>
          <div class="flex items-center gap-2 px-4 mb-4">
            <div class="h-6 w-40 bg-[var(--color-bg-elevated)] rounded animate-pulse"></div>
          </div>
          <div class="flex gap-4 px-4 overflow-hidden">
            {% for _ in range(4) %}
              <div class="w-64 flex-shrink-0">
                <div class="aspect-video bg-[var(--color-bg-elevated)] rounded-t-lg animate-pulse"></div>
                <div class="bg-[var(--color-bg-surface)] border border-t-0 border-[var(--border)] rounded-b-lg p-4">
                  <div class="h-5 w-3/4 bg-[var(--color-bg-elevated)] rounded animate-pulse mb-2"></div>
                  <div class="h-4 w-1/2 bg-[var(--color-bg-elevated)] rounded animate-pulse"></div>
                </div>
              </div>
            {% endfor %}
          </div>
        </div>

        {# Latest section skeleton #}
        <div>
          <div class="flex items-center gap-2 px-4 mb-4">
            <div class="h-6 w-32 bg-[var(--color-bg-elevated)] rounded animate-pulse"></div>
          </div>
          <div class="flex gap-4 px-4 overflow-hidden">
            {% for _ in range(4) %}
              <div class="w-64 flex-shrink-0">
                <div class="aspect-video bg-[var(--color-bg-elevated)] rounded-t-lg animate-pulse"></div>
                <div class="bg-[var(--color-bg-surface)] border border-t-0 border-[var(--border)] rounded-b-lg p-4">
                  <div class="h-5 w-3/4 bg-[var(--color-bg-elevated)] rounded animate-pulse mb-2"></div>
                  <div class="h-4 w-1/2 bg-[var(--color-bg-elevated)] rounded animate-pulse"></div>
                </div>
              </div>
            {% endfor %}
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
