/**
 * fragments/sample.html.ts - Outputs dist/fragments/sample.html
 *
 * Sample fragment for testing HTMX infrastructure.
 * This is a Jinja2 fragment template.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `<!-- Sample fragment for testing HTMX infrastructure -->
<div id="sample-fragment" data-testid="sample-fragment">
    <p>Sample fragment loaded successfully.</p>
    {% if is_htmx_request %}
    <p data-htmx="true">This is an HTMX request.</p>
    {% else %}
    <p data-htmx="false">This is a regular request.</p>
    {% endif %}
</div>
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
