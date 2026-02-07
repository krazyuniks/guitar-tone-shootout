/**
 * fragments/ping.html.ts - Outputs dist/fragments/ping.html
 *
 * Ping/pong fragment for testing HTMX connectivity.
 * This is a Jinja2 fragment template.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `<!-- Ping/pong fragment for testing HTMX connectivity -->
{% if is_htmx_request %}
<span id="ping-response" data-testid="ping-htmx">pong (htmx)</span>
{% else %}
<div id="ping-response" data-testid="ping-normal">
    <p>Ping endpoint is working.</p>
    <p>Send request with <code>HX-Request: true</code> header to get HTMX response.</p>
</div>
{% endif %}
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
