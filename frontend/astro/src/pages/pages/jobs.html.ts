/**
 * pages/jobs.html.ts - Outputs dist/pages/jobs.html
 *
 * Jobs list page — shows active and recent jobs for the authenticated user.
 * This is a Jinja2 template for the SSR page.
 */

import type { APIRoute } from 'astro';

// Import CSS so Tailwind scans this file's classes
import '../../styles/global.css';

export const GET: APIRoute = () => {
  const template = `{% extends "layouts/base.html" %}

{% block title %}Jobs - Guitar Tone Shootout{% endblock %}
{% block description %}View your active and recent processing jobs.{% endblock %}

{% block content %}
<div data-testid="jobs-page" class="min-h-screen">
  <div class="container mx-auto px-4 py-8 max-w-4xl">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-[var(--color-text-primary)] mb-2">
        Jobs
      </h1>
      <p class="text-[var(--color-text-secondary)]">
        Your active and recent processing jobs
      </p>
    </div>

    {% if jobs %}
      <div data-testid="job-list" class="space-y-4">
        {% for job in jobs %}
          <a
            href="/jobs/{{ job.id }}"
            data-testid="job-item"
            class="block bg-[var(--color-bg-surface)] rounded-lg border border-[var(--border)] p-5 hover:border-amber-500/30 transition-colors"
          >
            <div class="flex items-start justify-between gap-4">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-3 mb-2">
                  <span class="text-sm font-medium text-[var(--color-text-primary)]">
                    {{ job.job_type | replace('_', ' ') | title }}
                  </span>
                  <span class="px-2 py-0.5 rounded-full text-xs font-medium
                    {% if job.status == 'running' %}bg-blue-500/20 text-blue-400
                    {% elif job.status == 'completed' %}bg-green-500/20 text-green-400
                    {% elif job.status == 'failed' %}bg-red-500/20 text-red-400
                    {% elif job.status == 'pending' %}bg-yellow-500/20 text-yellow-400
                    {% else %}bg-gray-500/20 text-gray-400{% endif %}
                  " data-testid="job-status">
                    {{ job.status | capitalize }}
                  </span>
                </div>
                {% if job.message %}
                  <p class="text-sm text-[var(--color-text-secondary)] mb-2">{{ job.message }}</p>
                {% endif %}
                {% if job.status in ('running', 'pending') %}
                  <div class="w-full bg-[var(--color-bg-elevated)] rounded-full h-1.5 mb-2">
                    <div
                      class="bg-amber-500 h-1.5 rounded-full transition-all"
                      style="width: {{ job.progress }}%"
                    ></div>
                  </div>
                {% endif %}
              </div>
              <div class="text-right shrink-0">
                <div class="text-sm text-[var(--color-text-muted)]">{{ job.relative_time }}</div>
              </div>
            </div>
          </a>
        {% endfor %}
      </div>
    {% else %}
      <div class="text-center py-16 text-[var(--color-text-muted)]">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="w-12 h-12 mx-auto mb-4 opacity-40">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <p class="text-lg font-medium text-[var(--color-text-secondary)] mb-2">No jobs yet</p>
        <p class="text-sm">Start processing a shootout to see jobs here.</p>
      </div>
    {% endif %}
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
