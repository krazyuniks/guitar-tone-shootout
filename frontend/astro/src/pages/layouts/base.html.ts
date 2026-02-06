/**
 * Base Layout Template Generator
 *
 * This TypeScript file generates the Jinja2-compatible base layout template
 * that SSR pages can extend. It provides the HTML structure, CSS links,
 * HTMX, Alpine.js, and Jinja2 blocks for content and scripts.
 *
 * Build output: frontend/astro/dist/layouts/base.html
 * Usage in Jinja2: {% extends "layouts/base.html" %}
 */

export async function GET() {
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Guitar Tone Shootout{% endblock %}</title>

  <!-- Compiled Tailwind CSS with design tokens (hash injected by post-build script) -->
  <link rel="stylesheet" href="/_astro/CSS_PLACEHOLDER">

  <!-- HTMX for dynamic HTML fragments -->
  <script src="https://unpkg.com/htmx.org@1.9.10" integrity="sha384-D1Kt99CQMDuVetoL1lrYwg5t+9QdHe7NLX/SoJYkXDFfX37iInKRy5xLSi8nO7UC" crossorigin="anonymous"></script>

  <!-- Alpine.js for client-side interactivity -->
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
</head>
<body class="min-h-screen">
  {% block content %}
  <!-- SSR page content goes here -->
  {% endblock %}

  {% block scripts %}
  <!-- Page-specific scripts go here -->
  {% endblock %}
</body>
</html>`;

  return new Response(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
}
