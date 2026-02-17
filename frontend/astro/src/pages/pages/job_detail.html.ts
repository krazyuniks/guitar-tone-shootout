/**
 * pages/job_detail.html.ts - Outputs dist/pages/job_detail.html
 *
 * Job detail page — shows progress, status, and retry action.
 * This is a Jinja2 template for the SSR page.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `{% extends "layouts/base.html" %}

{% block title %}Job {{ job.id[:8] }} - Guitar Tone Shootout{% endblock %}
{% block description %}Job processing status and progress.{% endblock %}

{% block content %}
<div data-testid="job-detail" class="min-h-screen">
  <div class="container mx-auto px-4 py-8 max-w-2xl">
    <a
      href="/jobs"
      class="inline-flex items-center gap-2 text-[var(--color-text-secondary)] hover:text-amber-400 transition-colors mb-6"
    >
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
        <path fill-rule="evenodd" d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z" clip-rule="evenodd"/>
      </svg>
      Back to Jobs
    </a>

    <div class="bg-[var(--color-bg-surface)] rounded-lg border border-[var(--border)] p-6">
      <div class="flex items-start justify-between gap-4 mb-4">
        <div>
          <h1 class="text-xl font-bold text-[var(--color-text-primary)] mb-1">
            {{ job.job_type | replace('_', ' ') | title }}
          </h1>
          <p class="text-sm text-[var(--color-text-muted)] font-mono">{{ job.id }}</p>
        </div>
        <span class="px-3 py-1 rounded-full text-sm font-medium
          {% if job.status == 'running' %}bg-blue-500/20 text-blue-400
          {% elif job.status == 'completed' %}bg-green-500/20 text-green-400
          {% elif job.status == 'failed' %}bg-red-500/20 text-red-400
          {% elif job.status == 'pending' %}bg-yellow-500/20 text-yellow-400
          {% else %}bg-gray-500/20 text-gray-400{% endif %}
        " data-testid="job-status">
          {{ job.status | capitalize }}
        </span>
      </div>

      {% if job.status in ('running', 'pending') %}
        <div class="mb-4">
          <div class="flex justify-between text-sm text-[var(--color-text-secondary)] mb-1">
            <span>Progress</span>
            <span>{{ job.progress }}%</span>
          </div>
          <div class="w-full bg-[var(--color-bg-elevated)] rounded-full h-2">
            <div
              class="bg-amber-500 h-2 rounded-full transition-all"
              style="width: {{ job.progress }}%"
            ></div>
          </div>
        </div>
      {% endif %}

      {% if job.message %}
        <p class="text-sm text-[var(--color-text-secondary)] mb-4">{{ job.message }}</p>
      {% endif %}

      {% if job.error %}
        <div class="bg-red-500/10 border border-red-500/20 rounded-lg p-3 mb-4">
          <p class="text-sm text-red-400 font-mono whitespace-pre-wrap">{{ job.error }}</p>
        </div>
      {% endif %}

      <div class="text-sm text-[var(--color-text-muted)]">
        Created {{ job.relative_time }}
      </div>

      {% if job.status == 'failed' %}
        <div class="mt-6 pt-4 border-t border-[var(--border)]">
          <button
            data-testid="retry-job-btn"
            hx-post="/api/v1/jobs/{{ job.id }}/retry"
            hx-swap="none"
            hx-on::after-request="window.location.reload()"
            class="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-black font-medium rounded-lg transition-colors"
          >
            Retry Job
          </button>
        </div>
      {% endif %}
    </div>
  </div>
</div>
{% endblock %}
`;

  return new Response(template, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
    },
  });
};
