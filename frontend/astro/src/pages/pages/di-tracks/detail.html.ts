/**
 * Astro endpoint that serves the di-tracks/detail.html Jinja2 template.
 * This file is copied to dist/pages/di-tracks/ during build for FastAPI to serve.
 */
import type { APIRoute } from "astro";

const template = `{% extends "layouts/base.html" %}

{% block title %}{{ track.title }} - DI Track{% endblock %}

{% block head %}
<!-- Canonical URL -->
<link rel="canonical" href="{{ canonical_url }}">
{% endblock %}

{% block content %}
<div
  data-testid="di-track-detail-page"
  class="min-h-screen"
>
  <div class="container mx-auto px-4 py-6 max-w-4xl">
    <!-- Back link -->
    <a
      href="/di-tracks"
      class="inline-flex items-center text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] mb-6"
    >
      <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
      </svg>
      Browse DI Tracks
    </a>

    <!-- Track Header -->
    <div class="mb-8">
      <div class="flex flex-col md:flex-row gap-6">
        <!-- Waveform visualization placeholder -->
        <div class="flex-shrink-0 w-full md:w-64">
          <div class="aspect-video bg-[var(--color-bg-elevated)] rounded-lg flex items-center justify-center relative overflow-hidden">
            <!-- Simple CSS waveform representation -->
            <div class="flex items-center justify-center gap-0.5 w-full px-4">
              {% for i in range(50) %}
              <div
                class="w-1 bg-blue-500/70 rounded-full"
                style="height: {{ (i % 7 + 1) * 6 }}px;"
              ></div>
              {% endfor %}
            </div>
            <!-- Duration overlay -->
            <div class="absolute bottom-2 right-2 text-xs text-[var(--color-text-muted)] bg-[var(--color-bg-base)]/70 px-2 py-0.5 rounded">
              {{ track.duration_formatted }}
            </div>
          </div>
        </div>

        <!-- Track Info -->
        <div class="flex-1">
          <h1
            data-testid="track-detail-title"
            class="text-2xl font-bold text-[var(--color-text-primary)] mb-2"
          >
            {{ track.title }}
          </h1>

          <!-- Badges -->
          <div class="flex items-center gap-2 mb-4 flex-wrap">
            {% if track.is_system_track %}
            <span class="px-2 py-1 text-xs font-medium rounded bg-purple-500/20 text-purple-400">
              System Track
            </span>
            {% endif %}
            {% if track.is_public %}
            <span class="px-2 py-1 text-xs font-medium rounded bg-green-500/20 text-green-400">
              Public
            </span>
            {% else %}
            <span class="px-2 py-1 text-xs font-medium rounded bg-yellow-500/20 text-yellow-400">
              Private
            </span>
            {% endif %}
          </div>

          <!-- Stats -->
          <div
            data-testid="track-detail-stats"
            class="flex gap-4 text-sm text-[var(--color-text-secondary)] mb-4"
          >
            <span title="Duration">
              <svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
              {{ track.duration_formatted }}
            </span>
            <span title="Sample Rate">
              <svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"/>
              </svg>
              {{ track.sample_rate }} Hz
            </span>
          </div>

          <!-- Description -->
          {% if track.description %}
          <p class="text-[var(--color-text-secondary)] mb-4">
            {{ track.description }}
          </p>
          {% endif %}

          <!-- Uploader -->
          {% if track.uploader_username %}
          <div class="flex items-center gap-2 mb-4">
            {% if track.uploader_avatar %}
            <img
              src="{{ track.uploader_avatar }}"
              alt="{{ track.uploader_username }}"
              class="w-6 h-6 rounded-full"
            >
            {% else %}
            <div class="w-6 h-6 rounded-full bg-[var(--color-bg-secondary)] flex items-center justify-center">
              <span class="text-[10px] text-[var(--color-text-muted)]">
                {{ track.uploader_username[0]|upper }}
              </span>
            </div>
            {% endif %}
            <span class="text-sm text-[var(--color-text-secondary)]">
              {{ track.uploader_username }}
            </span>
            <span class="text-[var(--color-text-muted)]">&#183;</span>
            <span class="text-sm text-[var(--color-text-muted)]">
              {{ track.created_at }}
            </span>
          </div>
          {% endif %}

          <!-- Action buttons -->
          <div class="flex gap-3 flex-wrap">
            <!-- Use in Shootout button -->
            {% if user %}
            <a
              href="/shootout/create"
              data-astro-reload
              class="inline-flex items-center px-4 py-2 text-sm font-medium bg-[var(--color-accent-primary)] text-white rounded-lg hover:bg-[var(--color-accent-primary-hover)] transition-colors"
            >
              <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/>
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
              Use in Shootout
            </a>
            {% else %}
            <a
              href="/login?next=/di-tracks/{{ track.id }}"
              class="inline-flex items-center px-4 py-2 text-sm font-medium text-[var(--color-accent-primary)] border border-[var(--color-accent-primary)] rounded-lg hover:bg-[var(--color-accent-primary)] hover:text-white transition-colors"
            >
              Login to Use
            </a>
            {% endif %}
          </div>
        </div>
      </div>
    </div>

    <!-- Recording Metadata -->
    <div class="mb-8">
      <h2 class="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Recording Details</h2>
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {% if track.guitar %}
        <div class="bg-[var(--color-bg-surface)] rounded-lg p-4 border border-[var(--border)]">
          <span class="text-sm text-[var(--color-text-muted)] block mb-1">Guitar</span>
          <span class="text-[var(--color-text-primary)]">{{ track.guitar }}</span>
        </div>
        {% endif %}
        {% if track.pickups %}
        <div class="bg-[var(--color-bg-surface)] rounded-lg p-4 border border-[var(--border)]">
          <span class="text-sm text-[var(--color-text-muted)] block mb-1">Pickups</span>
          <span class="text-[var(--color-text-primary)]">{{ track.pickups }}</span>
        </div>
        {% endif %}
        {% if track.tuning %}
        <div class="bg-[var(--color-bg-surface)] rounded-lg p-4 border border-[var(--border)]">
          <span class="text-sm text-[var(--color-text-muted)] block mb-1">Tuning</span>
          <span class="text-[var(--color-text-primary)]">{{ track.tuning }}</span>
        </div>
        {% endif %}
        {% if track.strings %}
        <div class="bg-[var(--color-bg-surface)] rounded-lg p-4 border border-[var(--border)]">
          <span class="text-sm text-[var(--color-text-muted)] block mb-1">Strings</span>
          <span class="text-[var(--color-text-primary)]">{{ track.strings }}</span>
        </div>
        {% endif %}
        {% if track.recording_interface %}
        <div class="bg-[var(--color-bg-surface)] rounded-lg p-4 border border-[var(--border)]">
          <span class="text-sm text-[var(--color-text-muted)] block mb-1">Interface</span>
          <span class="text-[var(--color-text-primary)]">{{ track.recording_interface }}</span>
        </div>
        {% endif %}
        <div class="bg-[var(--color-bg-surface)] rounded-lg p-4 border border-[var(--border)]">
          <span class="text-sm text-[var(--color-text-muted)] block mb-1">Sample Rate</span>
          <span class="text-[var(--color-text-primary)]">{{ track.sample_rate }} Hz</span>
        </div>
        <div class="bg-[var(--color-bg-surface)] rounded-lg p-4 border border-[var(--border)]">
          <span class="text-sm text-[var(--color-text-muted)] block mb-1">Duration</span>
          <span class="text-[var(--color-text-primary)]">{{ track.duration_formatted }}</span>
        </div>
      </div>
    </div>

    <!-- Owner Actions -->
    {% if is_owner %}
    <div class="mb-8">
      <h2 class="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Manage Track</h2>
      <div class="bg-[var(--color-bg-surface)] rounded-lg p-4 border border-[var(--border)]">
        <div class="flex items-center justify-between">
          <div>
            <span class="text-[var(--color-text-primary)] font-medium">Public Visibility</span>
            <p class="text-sm text-[var(--color-text-muted)]">
              {% if track.is_public %}
              This track is visible to everyone.
              {% else %}
              This track is only visible to you.
              {% endif %}
            </p>
          </div>
          <button
            type="button"
            data-testid="toggle-public-btn"
            hx-post="/api/v1/di-tracks/{{ track.id }}/toggle-public"
            hx-swap="none"
            hx-on::after-request="window.location.reload()"
            class="px-4 py-2 text-sm font-medium rounded-lg transition-colors {% if track.is_public %}bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30{% else %}bg-green-500/20 text-green-400 hover:bg-green-500/30{% endif %}"
          >
            {% if track.is_public %}
            Make Private
            {% else %}
            Make Public
            {% endif %}
          </button>
        </div>
      </div>
    </div>
    {% endif %}
  </div>
</div>
{% endblock %}

{% block scripts %}
<script>
  // Handle HTMX response errors
  document.body.addEventListener('htmx:responseError', (event) => {
    const xhr = event.detail?.xhr;
    if (xhr && xhr.status === 401) {
      const currentPath = window.location.pathname;
      window.location.href = \`/login?next=\${encodeURIComponent(currentPath)}\`;
    }
  });
</script>
{% endblock %}`;

export const GET: APIRoute = () => {
  return new Response(template, {
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
};
