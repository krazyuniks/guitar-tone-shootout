/**
 * fragments/library/chains.html.ts - Outputs dist/fragments/library/chains.html
 *
 * Library Signal Chains List Fragment - displays a list of signal chains
 * or an empty state with guidance for creating chains.
 * This is a Jinja2 fragment template.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `<!-- Library Signal Chains List Fragment -->
<div data-testid="chain-list" data-empty="{{ 'true' if not chains else 'false' }}" class="space-y-3">
  {% if chains %}
    {% for chain in chains %}
      {% include 'fragments/library/chain_item.html' %}
    {% endfor %}
  {% else %}
    <div class="text-center py-12">
      <div class="text-gray-400 mb-2">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
        </svg>
      </div>
      <p class="text-gray-500">No signal chains yet</p>
      <p class="text-gray-400 text-sm mt-1">Create a signal chain to build your tone from amp + IR combos</p>
    </div>
  {% endif %}
</div>
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
