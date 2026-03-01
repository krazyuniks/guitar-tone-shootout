/**
 * pages/shootout_detail.html.ts - Outputs dist/pages/shootout_detail.html
 *
 * Shootout detail page.
 * This is a Jinja2 template for the SSR page.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `{% extends "layouts/base.html" %}

{% block title %}{{ title }} - Shootout{% endblock %}
{% block description %}View and compare guitar amp tones in this shootout comparison.{% endblock %}

{% block content %}
<div
  data-testid="shootout-detail-page"
  class="min-h-screen"
>
  <!-- Shootout detail rendered server-side -->
  {% include "fragments/shootouts/detail.html" %}
</div>
{% endblock %}

`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
