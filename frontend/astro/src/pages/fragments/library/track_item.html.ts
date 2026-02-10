/**
 * fragments/library/track_item.html.ts - Outputs dist/fragments/library/track_item.html
 *
 * Library DI Track Item Card with Expandable Waveform - displays a single DI track
 * with expand button, metadata (duration, sample rate, guitar, tuning, pickups),
 * delete button (for non-system tracks), and an expandable waveform visualization section.
 * Uses Alpine.js for expand/collapse state.
 * This is a Jinja2 fragment template.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `<!-- Library DI Track Item Card with Expandable Waveform -->
<div
  x-data="{ expanded: false }"
  data-testid="track-item"
  data-track-id="{{ track.id }}"
  class="bg-gray-800 rounded-lg overflow-hidden hover:bg-gray-700/50 transition-colors"
>
  <!-- Main Row -->
  <div class="p-4">
    <div class="flex items-start gap-4">
      <!-- Waveform/Audio Icon & Expand Button -->
      <button
        type="button"
        @click="expanded = !expanded"
        data-testid="track-expand-btn"
        class="flex-shrink-0 w-16 h-12 bg-gray-700 rounded flex items-center justify-center hover:bg-gray-600 transition-colors cursor-pointer"
        :aria-expanded="expanded"
        aria-label="Toggle waveform"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          class="h-6 w-6 text-blue-500 transition-transform"
          :class="{ 'rotate-90': expanded }"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
        </svg>
      </button>

      <!-- Audio Player -->
      <div class="flex-1 min-w-0 max-w-md">
        <audio
          data-testid="track-audio-player"
          controls
          class="w-full h-8"
          preload="metadata"
          src="/api/v1/di-tracks/{{ track.id }}/stream"
        >
          Your browser does not support the audio element.
        </audio>
      </div>

      <!-- Content -->
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2">
          <h3 class="text-white font-medium truncate">{{ track.title }}</h3>
          {% if track.is_public %}
            <span class="px-1.5 py-0.5 text-[10px] font-medium rounded bg-green-500/20 text-green-400">Public</span>
          {% else %}
            <span class="px-1.5 py-0.5 text-[10px] font-medium rounded bg-yellow-500/20 text-yellow-400">Private</span>
          {% endif %}
        </div>
        {% if track.description %}
          <p class="text-gray-400 text-sm truncate mt-1">{{ track.description }}</p>
        {% endif %}
        <div class="flex items-center flex-wrap gap-2 mt-2 text-xs">
          <span class="text-gray-500">{{ track.duration_formatted }}</span>
          <span class="text-gray-500">{{ track.sample_rate }} Hz</span>
          {% if track.guitar %}
            <span class="px-2 py-0.5 bg-gray-700 rounded text-gray-300">{{ track.guitar }}</span>
          {% endif %}
          {% if track.tuning %}
            <span class="px-2 py-0.5 bg-gray-700 rounded text-gray-300">{{ track.tuning }}</span>
          {% endif %}
          {% if track.pickups %}
            <span class="px-2 py-0.5 bg-gray-700 rounded text-gray-300">{{ track.pickups }}</span>
          {% endif %}
          {% if track.is_system_track %}
            <span class="text-purple-400">System Track</span>
          {% endif %}
        </div>
      </div>

      <!-- Action buttons -->
      <div class="flex-shrink-0 flex items-center gap-2">
        <!-- Library actions (only shown when is_library_view is true and user owns track) -->
        {% if is_library_view and not track.is_system_track %}
        <!-- Toggle Public Button -->
        <button
          type="button"
          data-testid="track-toggle-public-btn"
          hx-post="/api/v1/html/library/tracks/{{ track.id }}/toggle-public"
          hx-target="closest [data-testid='track-item']"
          hx-swap="outerHTML"
          class="p-2 text-gray-500 hover:text-blue-400 hover:bg-blue-500/10 rounded transition-colors"
          aria-label="Toggle visibility"
          title="{% if track.is_public %}Make private{% else %}Make public{% endif %}"
        >
          {% if track.is_public %}
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path d="M10 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z"/>
            <path fill-rule="evenodd" d="M.664 10.59a1.651 1.651 0 010-1.186A10.004 10.004 0 0110 3c4.257 0 7.893 2.66 9.336 6.41.147.381.146.804 0 1.186A10.004 10.004 0 0110 17c-4.257 0-7.893-2.66-9.336-6.41zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"/>
          </svg>
          {% else %}
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path fill-rule="evenodd" d="M3.28 2.22a.75.75 0 00-1.06 1.06l14.5 14.5a.75.75 0 101.06-1.06l-1.745-1.745a10.029 10.029 0 003.3-4.38 1.651 1.651 0 000-1.185A10.004 10.004 0 009.999 3a9.956 9.956 0 00-4.744 1.194L3.28 2.22zM7.752 6.69l1.092 1.092a2.5 2.5 0 013.374 3.373l1.091 1.092a4 4 0 00-5.557-5.557z" clip-rule="evenodd"/>
            <path d="M10.748 13.93l2.523 2.523a9.987 9.987 0 01-3.27.547c-4.258 0-7.894-2.66-9.337-6.41a1.651 1.651 0 010-1.186A10.007 10.007 0 012.839 6.02L6.07 9.252a4 4 0 004.678 4.678z"/>
          </svg>
          {% endif %}
        </button>

        <!-- Delete Button -->
        <button
          type="button"
          data-testid="track-delete-btn"
          onclick="handleDelete('/api/v1/di-tracks/{{ track.id }}', '{{ track.title | replace("'", "\\'") }}', '[data-track-id=\\'{{ track.id }}\\']')"
          class="p-2 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
          aria-label="Delete track"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path fill-rule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.52.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z" clip-rule="evenodd" />
          </svg>
        </button>
        {% endif %}

        <!-- Save to Library button (only shown in public view for logged-in users) -->
        {% if not is_library_view and user %}
        <button
          type="button"
          data-testid="track-save-btn"
          hx-post="/api/v1/html/library/tracks/{{ track.id }}/save"
          hx-swap="none"
          class="p-2 text-gray-500 hover:text-green-400 hover:bg-green-500/10 rounded transition-colors"
          aria-label="Save to library"
          title="Save to my library"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z" />
          </svg>
        </button>
        {% endif %}
      </div>
    </div>
  </div>

  <!-- Expandable Waveform Section -->
  <div
    x-show="expanded"
    x-collapse
    data-testid="track-waveform"
    class="border-t border-gray-700"
  >
    <div class="p-4 bg-gray-900/50">
      <!-- Waveform visualization placeholder -->
      <div class="h-20 bg-gray-800 rounded flex items-center justify-center relative overflow-hidden">
        <!-- Simple CSS waveform representation -->
        <div class="flex items-center justify-center gap-0.5 w-full px-4">
          {% for i in range(50) %}
          <div
            class="w-1 bg-blue-500/70 rounded-full"
            style="height: {{ (i % 7 + 1) * 8 }}px;"
          ></div>
          {% endfor %}
        </div>
        <!-- Duration overlay -->
        <div class="absolute bottom-1 right-2 text-xs text-gray-400 bg-gray-900/70 px-2 py-0.5 rounded">
          {{ track.duration_formatted }}
        </div>
      </div>

      <!-- Additional track metadata -->
      <div class="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div>
          <span class="text-gray-500 block">Sample Rate</span>
          <span class="text-gray-300">{{ track.sample_rate }} Hz</span>
        </div>
        <div>
          <span class="text-gray-500 block">Duration</span>
          <span class="text-gray-300">{{ track.duration_formatted }}</span>
        </div>
        {% if track.guitar %}
        <div>
          <span class="text-gray-500 block">Guitar</span>
          <span class="text-gray-300">{{ track.guitar }}</span>
        </div>
        {% endif %}
        {% if track.tuning %}
        <div>
          <span class="text-gray-500 block">Tuning</span>
          <span class="text-gray-300">{{ track.tuning }}</span>
        </div>
        {% endif %}
        {% if track.pickups %}
        <div>
          <span class="text-gray-500 block">Pickups</span>
          <span class="text-gray-300">{{ track.pickups }}</span>
        </div>
        {% endif %}
        <div>
          <span class="text-gray-500 block">Uploaded</span>
          <span class="text-gray-300">{{ track.relative_time }}</span>
        </div>
      </div>
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
