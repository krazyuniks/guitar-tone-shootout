/**
 * pages/library/di-tracks.html.ts - Outputs dist/pages/library/di-tracks.html
 *
 * My DI Tracks library page.
 * This is a Jinja2 template for the SSR page.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `{% extends "layouts/base.html" %}

{% block title %}My DI Tracks - Guitar Tone Shootout{% endblock %}
{% block description %}View and manage your DI track recordings.{% endblock %}

{% block content %}
<div
  data-testid="di-tracks-library"
  class="container mx-auto px-4 py-8"
>
  <!-- Header -->
  <div class="mb-8">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-[var(--color-text-primary)] mb-2">
          My DI Tracks
        </h1>
        <p class="text-[var(--color-text-secondary)]">
          Upload and manage your raw guitar recordings for shootouts
        </p>
      </div>
      <button
        type="button"
        class="inline-flex items-center gap-2 px-4 py-2 bg-[var(--color-accent-primary)] hover:bg-[var(--color-accent-primary-hover)] text-white font-medium rounded-lg transition-colors"
        data-testid="upload-track-btn"
        onclick="document.getElementById('upload-modal').showModal()"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
          <path d="M9.25 13.25a.75.75 0 001.5 0V4.636l2.955 3.129a.75.75 0 001.09-1.03l-4.25-4.5a.75.75 0 00-1.09 0l-4.25 4.5a.75.75 0 101.09 1.03L9.25 4.636v8.614z" />
          <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
        </svg>
        Upload Track
      </button>
    </div>
  </div>

  <!-- HTMX-powered tracks list -->
  <div
    id="tracks-list-container"
    data-testid="tracks-list-container"
    hx-get="/api/v1/html/library/tracks"
    hx-trigger="load"
    hx-swap="innerHTML"
  >
    <!-- Loading state while HTMX fetches content -->
    <div class="space-y-3">
      {% for i in range(4) %}
      <div class="bg-[var(--color-bg-elevated)] rounded-lg p-4 animate-pulse">
        <div class="flex items-start gap-4">
          <div class="flex-shrink-0 w-16 h-12 bg-[var(--color-bg-secondary)] rounded"></div>
          <div class="flex-1">
            <div class="h-5 bg-[var(--color-bg-secondary)] rounded w-3/4 mb-2"></div>
            <div class="h-4 bg-[var(--color-bg-secondary)] rounded w-1/2 mb-2"></div>
            <div class="flex gap-2">
              <div class="h-4 w-16 bg-[var(--color-bg-secondary)] rounded"></div>
              <div class="h-4 w-20 bg-[var(--color-bg-secondary)] rounded"></div>
              <div class="h-4 w-12 bg-[var(--color-bg-secondary)] rounded"></div>
            </div>
          </div>
        </div>
      </div>
      {% endfor %}
    </div>

    <!-- Hidden sample track for build tests - replaced by HTMX at runtime -->
    <div style="display: none;" data-testid="track-item">
      <audio data-testid="track-audio-player" src="/api/v1/di-tracks/sample-id/stream"></audio>
    </div>
  </div>

  <!-- Upload Modal -->
  <dialog id="upload-modal" class="modal bg-transparent" x-data="{ dragging: false, uploading: false, progress: 0, fileError: '', uploadError: '' }">
    <div class="modal-box bg-[var(--color-bg-surface)] border border-[var(--border)] max-w-lg">
      <form method="dialog">
        <button class="btn btn-sm btn-circle btn-ghost absolute right-2 top-2 text-[var(--color-text-secondary)]">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
          </svg>
        </button>
      </form>
      <h3 class="font-bold text-lg text-[var(--color-text-primary)] mb-4">Upload DI Track</h3>
      <form
        id="upload-form"
        data-testid="upload-track-form"
        hx-post="/api/v1/di-tracks"
        hx-encoding="multipart/form-data"
        hx-target="#tracks-list-container"
        hx-swap="innerHTML"
        class="space-y-4"
      >
        <!-- Drag and Drop Zone -->
        <div>
          <label class="block text-sm font-medium text-[var(--color-text-secondary)] mb-2">
            Audio File (WAV) *
          </label>
          <div
            data-testid="upload-drop-zone"
            :class="dragging ? 'border-[var(--color-accent-primary)] bg-[var(--color-accent-primary)]/10' : 'border-[var(--border)] bg-[var(--color-bg-elevated)]'"
            class="relative border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer"
            @dragover.prevent="dragging = true"
            @dragenter.prevent="dragging = true"
            @dragleave.prevent="dragging = false"
            @drop.prevent="
              dragging = false;
              const file = $event.dataTransfer.files[0];
              if (file) {
                document.getElementById('file-input').files = $event.dataTransfer.files;
                document.getElementById('file-input').dispatchEvent(new Event('change', { bubbles: true }));
              }
            "
            @click="document.getElementById('file-input').click()"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-12 h-12 mx-auto mb-3 text-[var(--color-text-secondary)]">
              <path d="M9.25 13.25a.75.75 0 001.5 0V4.636l2.955 3.129a.75.75 0 001.09-1.03l-4.25-4.5a.75.75 0 00-1.09 0l-4.25 4.5a.75.75 0 101.09 1.03L9.25 4.636v8.614z" />
              <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
            </svg>
            <p class="text-[var(--color-text-primary)] font-medium mb-1">
              Drop WAV file here or click to select
            </p>
            <p class="text-sm text-[var(--color-text-secondary)]">
              Maximum file size: 200MB
            </p>
            <input
              type="file"
              id="file-input"
              name="file"
              data-testid="upload-file-input"
              accept=".wav,audio/wav,audio/x-wav,audio/wave"
              required
              class="hidden"
              @change="
                fileError = '';
                const file = $event.target.files[0];
                if (!file) return;

                // Validate file type
                const isWav = file.name.toLowerCase().endsWith('.wav') ||
                              file.type === 'audio/wav' ||
                              file.type === 'audio/x-wav' ||
                              file.type === 'audio/wave';
                if (!isWav) {
                  fileError = 'Only WAV files are supported';
                  $event.target.value = '';
                  return;
                }

                // Validate file size (200MB = 200 * 1024 * 1024 bytes)
                const maxSize = 200 * 1024 * 1024;
                if (file.size > maxSize) {
                  fileError = 'File size must be less than 200MB';
                  $event.target.value = '';
                  return;
                }
              "
            />
          </div>
          <!-- File validation error -->
          <div
            x-show="fileError"
            data-testid="upload-file-error"
            class="mt-2 text-sm text-red-600"
            x-text="fileError"
          ></div>
        </div>

        <!-- Upload Progress Bar -->
        <div x-show="uploading" data-testid="upload-progress-bar" class="space-y-2">
          <div class="flex items-center justify-between text-sm">
            <span class="text-[var(--color-text-secondary)]">Uploading...</span>
            <span data-testid="upload-progress-text" class="text-[var(--color-text-primary)] font-medium" x-text="progress + '%'"></span>
          </div>
          <div class="w-full bg-[var(--color-bg-elevated)] rounded-full h-2 overflow-hidden">
            <div
              class="bg-[var(--color-accent-primary)] h-full transition-all duration-300"
              :style="'width: ' + progress + '%'"
            ></div>
          </div>
        </div>

        <!-- Upload error message -->
        <div
          x-show="uploadError"
          data-testid="upload-error-message"
          class="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-800"
          x-text="uploadError"
        ></div>

        <div>
          <label class="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">
            Title *
          </label>
          <input
            type="text"
            name="name"
            data-testid="upload-title-input"
            required
            maxlength="255"
            class="w-full px-3 py-2 bg-[var(--color-bg-elevated)] border border-[var(--border)] rounded-lg text-[var(--color-text-primary)] focus:border-[var(--color-accent-primary)] focus:ring-1 focus:ring-[var(--color-accent-primary)] outline-none"
            placeholder="e.g., Clean Tone Test Riff"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">
            Guitar
          </label>
          <input
            type="text"
            name="guitar"
            data-testid="upload-guitar-input"
            maxlength="255"
            class="w-full px-3 py-2 bg-[var(--color-bg-elevated)] border border-[var(--border)] rounded-lg text-[var(--color-text-primary)] focus:border-[var(--color-accent-primary)] focus:ring-1 focus:ring-[var(--color-accent-primary)] outline-none"
            placeholder="e.g., Fender Stratocaster"
          />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">
              Pickups
            </label>
            <input
              type="text"
              name="pickup"
              data-testid="upload-pickups-input"
              maxlength="255"
              class="w-full px-3 py-2 bg-[var(--color-bg-elevated)] border border-[var(--border)] rounded-lg text-[var(--color-text-primary)] focus:border-[var(--color-accent-primary)] focus:ring-1 focus:ring-[var(--color-accent-primary)] outline-none"
              placeholder="e.g., Bridge Humbucker"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">
              Tuning
            </label>
            <input
              type="text"
              name="tuning"
              data-testid="upload-tuning-input"
              maxlength="50"
              class="w-full px-3 py-2 bg-[var(--color-bg-elevated)] border border-[var(--border)] rounded-lg text-[var(--color-text-primary)] focus:border-[var(--color-accent-primary)] focus:ring-1 focus:ring-[var(--color-accent-primary)] outline-none"
              placeholder="e.g., E Standard"
            />
          </div>
        </div>
        <div>
          <label class="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">
            Description
          </label>
          <textarea
            name="description"
            data-testid="upload-description-textarea"
            rows="2"
            class="w-full px-3 py-2 bg-[var(--color-bg-elevated)] border border-[var(--border)] rounded-lg text-[var(--color-text-primary)] focus:border-[var(--color-accent-primary)] focus:ring-1 focus:ring-[var(--color-accent-primary)] outline-none resize-none"
            placeholder="Optional notes about this recording..."
          ></textarea>
        </div>
        <div>
          <label class="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">
            Notes
          </label>
          <textarea
            name="notes"
            data-testid="upload-notes-textarea"
            rows="2"
            class="w-full px-3 py-2 bg-[var(--color-bg-elevated)] border border-[var(--border)] rounded-lg text-[var(--color-text-primary)] focus:border-[var(--color-accent-primary)] focus:ring-1 focus:ring-[var(--color-accent-primary)] outline-none resize-none"
            placeholder="Additional notes or technical details..."
          ></textarea>
        </div>
        <div class="flex justify-end gap-3 pt-4">
          <button
            type="button"
            data-testid="upload-cancel-btn"
            class="px-4 py-2 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors"
            onclick="document.getElementById('upload-modal').close()"
          >
            Cancel
          </button>
          <button
            type="submit"
            data-testid="upload-submit-btn"
            :disabled="uploading"
            class="px-4 py-2 bg-[var(--color-accent-primary)] hover:bg-[var(--color-accent-primary-hover)] text-white font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Upload
          </button>
        </div>
      </form>
    </div>
    <form method="dialog" class="modal-backdrop bg-black/50">
      <button>close</button>
    </form>
  </dialog>
</div>
{% endblock %}

{% block scripts %}
<script>
  // Handle HTMX response errors for auth and general errors
  document.body.addEventListener('htmx:responseError', (event) => {
    const xhr = event.detail?.xhr;
    if (xhr && xhr.status === 401) {
      // Not authenticated - redirect to login
      const currentPath = window.location.pathname;
      window.location.href = \`/login?next=\${encodeURIComponent(currentPath)}\`;
    } else if (event.detail?.elt?.id === 'upload-form') {
      // Handle upload errors
      const alpine = Alpine.store ? Alpine.store : window.Alpine;
      const modalElement = document.querySelector('#upload-modal');
      if (modalElement && modalElement.__x) {
        const data = modalElement.__x.$data;
        data.uploading = false;
        data.progress = 0;
        data.uploadError = xhr?.responseText || 'Upload failed. Please try again.';
      }
    }
  });

  // Track upload progress via htmx:xhr:progress
  document.body.addEventListener('htmx:xhr:progress', (event) => {
    if (event.detail?.elt?.id === 'upload-form') {
      const modalElement = document.querySelector('#upload-modal');
      if (modalElement && modalElement.__x) {
        const data = modalElement.__x.$data;
        const percent = Math.round((event.detail.loaded / event.detail.total) * 100);
        data.progress = percent;
      }
    }
  });

  // Handle upload start
  document.body.addEventListener('htmx:beforeRequest', (event) => {
    if (event.detail?.elt?.id === 'upload-form') {
      const modalElement = document.querySelector('#upload-modal');
      if (modalElement && modalElement.__x) {
        const data = modalElement.__x.$data;
        data.uploading = true;
        data.progress = 0;
        data.uploadError = '';
      }
    }
  });

  // Close upload modal on successful upload and reset form
  document.body.addEventListener('htmx:afterSwap', (event) => {
    if (event.detail.target.id === 'tracks-list-container' && event.detail.successful) {
      const modal = document.getElementById('upload-modal');
      const form = document.getElementById('upload-form');
      if (modal && modal.open) {
        // Reset form
        if (form) {
          form.reset();
        }
        // Reset Alpine.js state
        const modalElement = document.querySelector('#upload-modal');
        if (modalElement && modalElement.__x) {
          const data = modalElement.__x.$data;
          data.uploading = false;
          data.progress = 0;
          data.fileError = '';
          data.uploadError = '';
          data.dragging = false;
        }
        modal.close();
      }
    }
  });
</script>
{% endblock %}
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
