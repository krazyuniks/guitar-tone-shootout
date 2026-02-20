/**
 * fragments/gear/public_pack_card.html.ts - Outputs dist/fragments/gear/public_pack_card.html
 *
 * Public gear pack card component.
 * This is a Jinja2 fragment template.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `<!-- Public Gear Pack Card (STORY-002)
     - No expandable accordion
     - Title links to /gear/{slug} (SEO-friendly URL)
     - No model checkboxes (those are on the detail page)
-->
{% set gear_styles = {
  'amp': {'bg': 'bg-orange-500/10', 'label': 'Amp Head Capture'},
  'full-rig': {'bg': 'bg-orange-500/10', 'label': 'Full Rig / Combo Capture'},
  'ir': {'bg': 'bg-green-500/10', 'label': 'Cabinet IR'},
  'pedal': {'bg': 'bg-purple-500/10', 'label': 'Pedal Capture'},
  'outboard': {'bg': 'bg-blue-500/10', 'label': 'Outboard Gear'}
} %}
{% set styles = gear_styles.get(pack.gear_type, {'bg': 'bg-gray-500/10', 'label': pack.gear_type|title}) %}

{% set platform_styles = {
  'nam': {'bg': 'bg-amber-500/25', 'text': 'text-amber-500'},
  'aida-x': {'bg': 'bg-purple-500/25', 'text': 'text-purple-500'},
  'ir': {'bg': 'bg-green-500/25', 'text': 'text-green-500'}
} %}
{% set platform = platform_styles.get(pack.platform, {'bg': 'bg-gray-500/25', 'text': 'text-gray-400'}) %}

<div
  data-testid="gear-pack-card"
  data-pack-id="{{ pack.id }}"
  data-pack-slug="{{ pack.slug }}"
  class="border border-[var(--border)] rounded-lg overflow-hidden bg-[var(--color-bg-elevated)] hover:border-[var(--border-hover)] transition-colors"
>
  <!-- Main card content - horizontal layout -->
  <div class="flex">
    <!-- Image section (left) -->
    <a
      href="/gear/{{ pack.slug }}"

      class="flex-shrink-0 w-28 sm:w-36"
      data-testid="pack-image-link"
    >
      {% if pack.image_url %}
        <img
          src="{{ pack.image_url }}"
          alt="{{ pack.title }}"
          class="w-full h-full object-cover aspect-square"
          loading="lazy"
        />
      {% else %}
        <!-- Placeholder with gear type icon -->
        <div class="w-full h-full aspect-square flex flex-col items-center justify-center p-2 {{ styles.bg }}">
          {% if pack.gear_type == 'amp' %}
            <!-- Amp head icon -->
            <svg viewBox="0 0 100 100" fill="currentColor" class="w-full h-full max-w-[90%] max-h-[90%] text-white/40" preserveAspectRatio="xMidYMid meet">
              <rect x="0" y="5" width="100" height="90" rx="3" fill="#1a1a1a"/>
              <rect x="2" y="7" width="96" height="86" rx="2" fill="#0d0d0d" stroke="#333" stroke-width="1"/>
              <rect x="5" y="10" width="90" height="20" rx="1" fill="#1f1f1f"/>
              <circle cx="15" cy="20" r="5" fill="#333" stroke="#555" stroke-width="1"/>
              <circle cx="32" cy="20" r="5" fill="#333" stroke="#555" stroke-width="1"/>
              <circle cx="50" cy="20" r="5" fill="#333" stroke="#555" stroke-width="1"/>
              <circle cx="68" cy="20" r="5" fill="#333" stroke="#555" stroke-width="1"/>
              <circle cx="85" cy="20" r="5" fill="#333" stroke="#555" stroke-width="1"/>
              <circle cx="8" cy="12" r="2" fill="#22c55e"/>
              <rect x="5" y="33" width="90" height="55" rx="2" fill="#0a0a0a"/>
              <rect x="15" y="52" width="70" height="18" rx="2" fill="#1a1a1a" stroke="#333" stroke-width="0.5"/>
              <text x="50" y="65" text-anchor="middle" font-size="12" fill="#888" font-family="sans-serif" font-weight="bold">AMP MODEL</text>
            </svg>
          {% elif pack.gear_type == 'full-rig' %}
            <!-- Full rig icon (amp head + cabinet) -->
            <svg viewBox="0 0 100 100" fill="currentColor" class="w-full h-full max-w-[90%] max-h-[90%] text-white/40" preserveAspectRatio="xMidYMid meet">
              <!-- Amp head (top) -->
              <rect x="5" y="2" width="90" height="38" rx="3" fill="#1a1a1a"/>
              <rect x="7" y="4" width="86" height="34" rx="2" fill="#0d0d0d" stroke="#333" stroke-width="0.5"/>
              <rect x="10" y="7" width="80" height="10" rx="1" fill="#1f1f1f"/>
              <circle cx="18" cy="12" r="3" fill="#333" stroke="#555" stroke-width="0.5"/>
              <circle cx="30" cy="12" r="3" fill="#333" stroke="#555" stroke-width="0.5"/>
              <circle cx="42" cy="12" r="3" fill="#333" stroke="#555" stroke-width="0.5"/>
              <circle cx="54" cy="12" r="3" fill="#333" stroke="#555" stroke-width="0.5"/>
              <circle cx="66" cy="12" r="3" fill="#333" stroke="#555" stroke-width="0.5"/>
              <circle cx="11" cy="7" r="1.5" fill="#22c55e"/>
              <rect x="10" y="20" width="80" height="15" rx="1" fill="#0a0a0a"/>
              <!-- Cabinet (bottom) -->
              <rect x="3" y="44" width="94" height="54" rx="3" fill="#1a1a1a"/>
              <rect x="5" y="46" width="90" height="50" rx="2" fill="#0d0d0d" stroke="#333" stroke-width="0.5"/>
              <circle cx="50" cy="65" r="18" fill="#1f1f1f"/>
              <circle cx="50" cy="65" r="14" fill="#2a2a2a"/>
              <circle cx="50" cy="65" r="5" fill="#1a1a1a" stroke="#333" stroke-width="0.5"/>
              <rect x="15" y="82" width="70" height="14" rx="2" fill="#1a1a1a" stroke="#333" stroke-width="0.5"/>
              <text x="50" y="93" text-anchor="middle" font-size="12" fill="#888" font-family="sans-serif" font-weight="bold">FULL RIG</text>
            </svg>
          {% elif pack.gear_type == 'ir' %}
            <!-- Speaker/IR icon -->
            <svg viewBox="0 0 100 100" fill="currentColor" class="w-full h-full max-w-[90%] max-h-[90%] text-white/40" preserveAspectRatio="xMidYMid meet">
              <circle cx="50" cy="50" r="48" fill="#1a1a1a"/>
              <circle cx="50" cy="50" r="42" fill="#1f1f1f"/>
              <circle cx="50" cy="50" r="36" fill="#3d3d3d"/>
              <circle cx="50" cy="50" r="14" fill="#2d2d2d"/>
              <circle cx="50" cy="50" r="12" fill="#252525" stroke="#333" stroke-width="0.5"/>
              <text x="50" y="47" text-anchor="middle" font-size="7" fill="#f5c518" font-family="sans-serif" font-weight="bold" font-style="italic">IMPULSE</text>
              <text x="50" y="56" text-anchor="middle" font-size="7" fill="#f5c518" font-family="sans-serif" font-weight="bold" font-style="italic">RESPONSE</text>
            </svg>
          {% elif pack.gear_type == 'pedal' %}
            <!-- Pedal icon -->
            <svg viewBox="0 0 100 100" fill="currentColor" class="w-full h-full max-w-[90%] max-h-[90%] text-white/40" preserveAspectRatio="xMidYMid meet">
              <rect x="5" y="0" width="90" height="100" rx="5" fill="#1a1a1a"/>
              <rect x="12" y="7" width="76" height="86" rx="3" fill="#0d0d0d"/>
              <circle cx="28" cy="22" r="8" fill="#2a2a2a" stroke="#444" stroke-width="1"/>
              <circle cx="50" cy="22" r="8" fill="#2a2a2a" stroke="#444" stroke-width="1"/>
              <circle cx="72" cy="22" r="8" fill="#2a2a2a" stroke="#444" stroke-width="1"/>
              <rect x="12" y="34" width="76" height="24" rx="2" fill="#1a1a1a" stroke="#333" stroke-width="0.5"/>
              <text x="50" y="50" text-anchor="middle" font-size="12" fill="#888" font-family="sans-serif" font-weight="bold">PEDAL</text>
              <circle cx="50" cy="65" r="3" fill="#22c55e"/>
              <ellipse cx="50" cy="82" rx="22" ry="10" fill="#2a2a2a" stroke="#444" stroke-width="1"/>
            </svg>
          {% else %}
            <!-- Default gear icon -->
            <svg viewBox="0 0 48 48" fill="currentColor" class="w-full h-full max-w-[90%] max-h-[90%] text-white/40">
              <circle cx="24" cy="24" r="16" fill-opacity="0.2"/>
              <circle cx="24" cy="24" r="8" fill-opacity="0.3"/>
            </svg>
          {% endif %}
        </div>
      {% endif %}
    </a>

    <!-- Content section (right) -->
    <div class="flex-1 p-3 sm:p-4 flex flex-col min-w-0">
      <!-- Title (clickable link) -->
      <a
        href="/gear/{{ pack.slug }}"

        data-testid="pack-title-link"
        class="group"
      >
        <h3
          data-testid="pack-title"
          class="font-semibold text-[var(--color-text-primary)] text-sm sm:text-base line-clamp-2 mb-1 group-hover:text-[var(--color-accent-primary)] transition-colors"
        >
          {{ pack.title }}
        </h3>
      </a>

      <!-- Subtitle: Gear type + Platform badge -->
      <div class="flex items-center gap-2 mb-2 flex-wrap">
        <span data-testid="pack-gear-type" class="text-sm font-medium text-[var(--color-text-primary)] opacity-80">
          {{ styles.label }}
        </span>
        <span
          data-testid="pack-platform-badge"
          class="inline-flex px-2 py-0.5 rounded text-xs font-semibold {{ platform.bg }} {{ platform.text }}"
        >
          {{ pack.platform|upper }}
        </span>
      </div>

      <!-- Stats row: Downloads, Favorites, Models count -->
      <div class="flex items-center gap-4 text-sm text-[var(--color-text-secondary)] mb-2">
        <span class="flex items-center gap-1">
          <!-- Download icon -->
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4">
            <path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z"/>
            <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z"/>
          </svg>
          {{ pack.downloads_count | format_number }}
        </span>
        <span class="flex items-center gap-1">
          <!-- Heart icon -->
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4">
            <path d="M9.653 16.915l-.005-.003-.019-.01a20.759 20.759 0 01-1.162-.682 22.045 22.045 0 01-2.582-1.9C4.045 12.733 2 10.352 2 7.5a4.5 4.5 0 018-2.828A4.5 4.5 0 0118 7.5c0 2.852-2.044 5.233-3.885 6.82a22.049 22.049 0 01-3.744 2.582l-.019.01-.005.003h-.002a.739.739 0 01-.69.001l-.002-.001z"/>
          </svg>
          {{ pack.favorites_count | format_number }}
        </span>
        <span data-testid="pack-models-count" class="flex items-center gap-1">
          <!-- Cube icon -->
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4">
            <path d="M10.362 1.093a.75.75 0 00-.724 0L2.523 5.018 10 9.143l7.477-4.125-7.115-3.925zM18 6.443l-7.25 4v8.25l6.862-3.786A.75.75 0 0018 14.25V6.443zm-8.75 12.25v-8.25l-7.25-4v7.807a.75.75 0 00.388.657l6.862 3.786z"/>
          </svg>
          {{ pack.models_count | format_number }} {{ 'model' if pack.models_count == 1 else 'models' }}
        </span>
      </div>

      <!-- Creator row -->
      <div class="flex items-center gap-2 mt-auto">
        {% if pack.creator_username %}
          <a
            href="https://www.tone3000.com/{{ pack.creator_username }}"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-center gap-1.5 hover:opacity-80 transition-opacity"
          >
            {% if pack.creator_avatar %}
              <img
                src="{{ pack.creator_avatar }}"
                alt="{{ pack.creator_username }}"
                class="w-5 h-5 rounded-full object-cover"
                loading="lazy"
              />
            {% else %}
              <div class="w-5 h-5 rounded-full bg-[var(--color-bg-secondary)] flex items-center justify-center">
                <span class="text-[10px] text-[var(--color-text-muted)]">
                  {{ pack.creator_username[0]|upper }}
                </span>
              </div>
            {% endif %}
            <span class="text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-accent-primary)]">
              {{ pack.creator_username }}
            </span>
          </a>
          {% if pack.relative_time %}
            <span class="text-[var(--color-text-muted)]">&#183;</span>
          {% endif %}
        {% endif %}
        {% if pack.relative_time %}
          <span class="text-xs text-[var(--color-text-muted)]" data-testid="pack-relative-time">
            {{ pack.relative_time }}
          </span>
        {% endif %}
      </div>
    </div>
  </div>

  <!-- Card actions bar - no expand toggle, just View Details link -->
  <div class="border-t border-[var(--border)] bg-[var(--color-bg-secondary)] px-3 py-2">
    <div class="flex items-center justify-between">
      <!-- Links -->
      <div class="flex items-center gap-3">
        <!-- View Details link (to /gear/{slug}) -->
        <a
          href="/gear/{{ pack.slug }}"

          class="text-xs text-[var(--color-accent-primary)] hover:text-[var(--color-accent-secondary)] transition-colors font-medium"
          data-testid="view-details-link"
        >
          View Details
        </a>
        <!-- View on T3K link -->
        <a
          href="https://www.tone3000.com/tones/{{ pack.source_record_id or pack.id }}"
          target="NAM"
          class="text-xs text-[var(--color-accent-primary)] hover:text-[var(--color-accent-secondary)] transition-colors flex items-center gap-1"
        >
          View on T3K
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4 inline-block ml-1">
            <path fill-rule="evenodd" d="M4.25 5.5a.75.75 0 00-.75.75v8.5c0 .414.336.75.75.75h8.5a.75.75 0 00.75-.75v-4a.75.75 0 011.5 0v4A2.25 2.25 0 0112.75 17h-8.5A2.25 2.25 0 012 14.75v-8.5A2.25 2.25 0 014.25 4h5a.75.75 0 010 1.5h-5z" clip-rule="evenodd"/>
            <path fill-rule="evenodd" d="M6.194 12.753a.75.75 0 001.06.053L16.5 4.44v2.81a.75.75 0 001.5 0v-4.5a.75.75 0 00-.75-.75h-4.5a.75.75 0 000 1.5h2.553l-9.056 8.194a.75.75 0 00-.053 1.06z" clip-rule="evenodd"/>
          </svg>
        </a>
      </div>

      <!-- No expand toggle on public view -->
    </div>
  </div>
</div>
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
