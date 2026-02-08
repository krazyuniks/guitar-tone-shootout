/**
 * pages/gear.html.ts - Outputs dist/pages/gear.html
 *
 * Browse gear page (public gear browsing).
 * Full SSR — all data rendered server-side, no HTMX.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `{% extends "layouts/base.html" %}

{% block title %}Browse Gear - Guitar Tone Shootout{% endblock %}
{% block description %}Discover amp, pedal, and cabinet captures from Tone3000{% endblock %}

{% block content %}
<div data-testid="gear-browse-page" class="min-h-screen">
  <div class="container mx-auto px-4 py-8">
    <div class="mb-8">
      <h1 data-testid="gear-browse-heading" class="text-2xl font-bold text-[var(--color-text-primary)] mb-2">
        Browse Gear
      </h1>
      <p class="text-[var(--color-text-secondary)]">
        Discover amp, pedal, and cabinet captures from Tone3000
      </p>
    </div>
    <div class="mb-6 space-y-4">
      <div class="flex flex-wrap gap-4 mb-4">
        <select name="gear_type" data-testid="gear-type-filter" hx-get="/fragments/gear/list" hx-target="#gear-list-container" hx-swap="innerHTML" class="rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--border)] px-3 py-2 text-[var(--color-text-primary)]">
          <option value="">All Types</option>
          <option value="amp">Amps</option>
          <option value="pedal">Pedals</option>
          <option value="ir">IRs</option>
        </select>
        <select name="manufacturer" data-testid="manufacturer-filter" hx-get="/fragments/gear/list" hx-target="#gear-list-container" hx-swap="innerHTML" class="rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--border)] px-3 py-2 text-[var(--color-text-primary)]">
          <option value="">All Manufacturers</option>
        </select>
        <input type="text" name="search" placeholder="Search gear..." data-testid="gear-search-input" hx-get="/fragments/gear/list" hx-target="#gear-list-container" hx-trigger="keyup changed delay:300ms" class="flex-1 rounded-lg bg-[var(--color-bg-elevated)] border border-[var(--border)] px-3 py-2 text-[var(--color-text-primary)]" />
      </div>
    </div>
    <div id="gear-list-container" data-testid="gear-list-container">
      {% include 'fragments/gear/public_browse.html' %}
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
