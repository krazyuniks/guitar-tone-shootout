/**
 * Gear Card Fragment Template
 *
 * Individual gear card component used in lists.
 * Can be used standalone or included in list fragments.
 *
 * Build output: frontend/astro/dist/fragments/gear/card.html
 * FastAPI route: templates.TemplateResponse(request, "fragments/gear/card.html", {"gear": gear})
 * Jinja2 include: {% include "fragments/gear/card.html" %}
 */

export async function GET() {
  const html = `<!-- Gear Card -->
<div
  data-testid="gear-card"
  data-gear-id="{{ gear.id }}"
  class="bg-[var(--color-bg-elevated)] rounded-lg p-6 hover:shadow-lg transition-shadow"
>
  <div class="flex gap-4">
    <!-- Thumbnail (if available) -->
    {% if gear.thumbnail_url %}
    <div class="flex-shrink-0">
      <img
        src="{{ gear.thumbnail_url }}"
        alt="{{ gear.name }}"
        class="w-24 h-24 object-cover rounded-lg"
      />
    </div>
    {% endif %}

    <!-- Gear Info -->
    <div class="flex-1">
      <h3 class="text-[var(--color-text-primary)] font-bold text-xl mb-2">
        <a
          href="/gear/{{ gear.slug }}"
          class="hover:text-[var(--color-accent-primary)]"
        >
          {{ gear.name }}
        </a>
      </h3>

      <div class="flex gap-4 text-sm mb-2">
        <span class="text-[var(--color-text-secondary)]">
          Type: <span class="text-[var(--color-text-primary)]">{{ gear.gear_type }}</span>
        </span>
        {% if gear.manufacturer %}
        <span class="text-[var(--color-text-secondary)]">
          By: <span class="text-[var(--color-text-primary)]">{{ gear.manufacturer }}</span>
        </span>
        {% endif %}
      </div>

      {% if gear.description %}
      <p class="text-[var(--color-text-secondary)] text-sm line-clamp-2">
        {{ gear.description }}
      </p>
      {% endif %}

      <!-- Tags -->
      {% if gear.tags %}
      <div class="mt-2 flex gap-2 flex-wrap">
        {% for tag in gear.tags %}
        <span class="bg-[var(--color-bg-base)] px-2 py-1 rounded text-xs text-[var(--color-text-primary)]">
          {{ tag }}
        </span>
        {% endfor %}
      </div>
      {% endif %}
    </div>

    <!-- Action Button -->
    <div class="flex-shrink-0 flex items-center">
      <a
        href="/gear/{{ gear.slug }}"
        class="bg-[var(--color-accent-primary)] text-white px-4 py-2 rounded-lg hover:opacity-90"
      >
        View Details
      </a>
    </div>
  </div>
</div>
`;

  return new Response(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
}
