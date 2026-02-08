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
      <h1 class="text-2xl font-bold text-[var(--color-text-primary)] mb-2">
        Browse Gear
      </h1>
      <p class="text-[var(--color-text-secondary)]">
        Discover amp, pedal, and cabinet captures from Tone3000
      </p>
    </div>
    {% include 'fragments/gear/public_browse.html' %}
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
