/**
 * pages/library/my_gear.html.ts - Outputs dist/pages/library/my_gear.html
 *
 * My Gear library page.
 * This is a Jinja2 template for the SSR page.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `{% extends "layouts/base.html" %}

{% block title %}My Gear - Guitar Tone Shootout{% endblock %}
{% block description %}Manage your saved gear library.{% endblock %}

{% block content %}
<div
  data-testid="my-gear-page"
  hx-boost="true"
  class="min-h-screen"
>
  <!-- Page Header -->
  <div class="container mx-auto px-4 py-8">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-[var(--color-text-primary)] mb-2">
        My Gear
      </h1>
      <p class="text-[var(--color-text-secondary)]">
        Manage your saved gear library
      </p>
    </div>

    <!-- My gear results rendered server-side -->
    {% include "fragments/library/my_gear.html" %}
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
