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
  {# Sections rendered server-side #}
  {% include "fragments/shootouts/sections.html" %}
</div>
{% endblock %}
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
