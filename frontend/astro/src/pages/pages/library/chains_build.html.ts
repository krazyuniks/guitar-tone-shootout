/**
 * Chain Builder Page Template
 *
 * Protected page for creating and editing signal chains.
 * Mounts React SignalChainBuilder component as an island.
 *
 * Build output: frontend/astro/dist/pages/library/chains_build.html
 * FastAPI route: templates.TemplateResponse(request, "pages/library/chains_build.html", {...})
 */

export async function GET() {
  const html = `{% extends "layouts/base.html" %}

{% block title %}Build Chain - Guitar Tone Shootout{% endblock %}

{% block content %}
<div
  data-testid="chain-builder-page"
  class="container mx-auto px-4 py-8"
>
  <div class="flex justify-between items-center mb-6">
    <h1
      class="text-[var(--color-text-primary)] text-3xl font-bold"
    >
      {% if chain_id %}Edit Chain{% else %}Build Chain{% endif %}
    </h1>
    <a
      href="/library/chains"
      data-astro-reload
      class="px-4 py-2 text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-elevated)] rounded-lg"
    >
      Back to Chains
    </a>
  </div>

  <!-- React Mount Point -->
  <div
    id="signal-chain-builder-mount"
    data-testid="chain-builder-mount"
    data-chain-id="{{ chain_id or '' }}"
    class="min-h-[600px]"
  >
    <!-- React component will mount here -->
  </div>
</div>

<!-- React Component Script -->
<script type="module">
  import { SignalChainBuilder } from '/_astro/SignalChainBuilder.js';
  import { createElement } from 'react';
  import { createRoot } from 'react-dom/client';

  // Get mount point and props
  const mountPoint = document.getElementById('signal-chain-builder-mount');
  const chainId = mountPoint?.getAttribute('data-chain-id') || null;

  // Mount React component
  if (mountPoint) {
    const root = createRoot(mountPoint);
    root.render(
      createElement(SignalChainBuilder, {
        mode: 'single',
        chainId: chainId || undefined,
        onSave: (chain) => {
          console.log('Chain saved:', chain);
          // Redirect to chains list after save
          window.location.href = '/library/chains';
        },
      })
    );
  }
</script>
{% endblock %}
`;

  return new Response(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
}
