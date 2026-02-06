/**
 * Gear Detail Page Template
 *
 * Public-facing gear detail page showing full information about a gear item.
 * Full page template served by FastAPI's Jinja2 renderer.
 *
 * Build output: frontend/astro/dist/pages/gear_detail.html
 * FastAPI route: templates.TemplateResponse(request, "pages/gear_detail.html", {"gear": gear})
 */

export async function GET() {
  const html = `{% extends "layouts/base.html" %}

{% block title %}{{ gear.name }} - Guitar Tone Shootout{% endblock %}

{% block content %}
<div
  data-testid="gear-detail-page"
  class="container mx-auto px-4 py-8"
>
  <!-- Back Link -->
  <div class="mb-6">
    <a
      href="/gear"
      data-testid="back-to-browse-link"
      class="text-[var(--color-accent-primary)] hover:underline"
    >
      ← Back to Browse
    </a>
  </div>

  <!-- Gear Details -->
  <div class="bg-[var(--color-bg-elevated)] rounded-lg p-6">
    <!-- Gear Name -->
    <h1
      data-testid="gear-detail-name"
      class="text-[var(--color-text-primary)] text-3xl font-bold mb-4"
    >
      {{ gear.name }}
    </h1>

    <!-- Gear Type -->
    <div class="mb-4">
      <span class="text-[var(--color-text-secondary)] font-semibold mr-2">Type:</span>
      <span
        data-testid="gear-detail-type"
        class="text-[var(--color-text-primary)]"
      >
        {{ gear.gear_type }}
      </span>
    </div>

    <!-- Manufacturer -->
    {% if gear.manufacturer %}
    <div class="mb-4">
      <span class="text-[var(--color-text-secondary)] font-semibold mr-2">Manufacturer:</span>
      <span
        data-testid="gear-detail-manufacturer"
        class="text-[var(--color-text-primary)]"
      >
        {{ gear.manufacturer }}
      </span>
    </div>
    {% endif %}

    <!-- Description -->
    {% if gear.description %}
    <div class="mb-4">
      <h2 class="text-[var(--color-text-secondary)] font-semibold mb-2">Description</h2>
      <p
        data-testid="gear-detail-description"
        class="text-[var(--color-text-primary)]"
      >
        {{ gear.description }}
      </p>
    </div>
    {% endif %}

    <!-- Thumbnail -->
    {% if gear.thumbnail_url %}
    <div class="mb-4">
      <img
        src="{{ gear.thumbnail_url }}"
        alt="{{ gear.name }}"
        class="max-w-md rounded-lg"
      />
    </div>
    {% endif %}

    <!-- Tags -->
    {% if gear.tags %}
    <div class="mb-4">
      <span class="text-[var(--color-text-secondary)] font-semibold mr-2">Tags:</span>
      <div class="inline-flex gap-2 flex-wrap">
        {% for tag in gear.tags %}
        <span class="bg-[var(--color-bg-base)] px-3 py-1 rounded-full text-sm text-[var(--color-text-primary)]">
          {{ tag }}
        </span>
        {% endfor %}
      </div>
    </div>
    {% endif %}

    <!-- Models -->
    {% if gear.models %}
    <div class="mt-6">
      <h2 class="text-[var(--color-text-secondary)] font-semibold mb-3">Available Models</h2>
      <div class="space-y-2">
        {% for model in gear.models %}
        <div class="bg-[var(--color-bg-base)] p-4 rounded-lg">
          <div class="flex justify-between items-center">
            <div>
              <span class="text-[var(--color-text-primary)] font-medium">{{ model.platform }}</span>
              {% if model.size %}
              <span class="text-[var(--color-text-secondary)] text-sm ml-2">({{ model.size }} bytes)</span>
              {% endif %}
            </div>
            {% if model.download_url %}
            <a
              href="{{ model.download_url }}"
              class="bg-[var(--color-accent-primary)] text-white px-4 py-2 rounded-lg hover:opacity-90"
            >
              Download
            </a>
            {% endif %}
          </div>
        </div>
        {% endfor %}
      </div>
    </div>
    {% endif %}
  </div>
</div>
{% endblock %}
`;

  return new Response(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
}
