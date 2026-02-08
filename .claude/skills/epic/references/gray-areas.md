# Gray Area Detection Patterns

GTS-specific patterns for identifying which areas need discussion.

## Keyword Detection

Based on feature keywords, suggest relevant GTS areas:

### GTS Domain-Specific Patterns

| Keywords | Suggested Areas |
|----------|-----------------|
| signal chain, chain, block, processing | signal_chain, audio_processing, gear_model |
| amp, pedal, ir, cabinet, capture, nam | gear_model, signal_chain, dual_database |
| shootout, compare, comparison, a/b | signal_chain, audio_processing, job_processing, frontend_layers |
| gear, library, collection, my gear | gear_model, frontend_layers, data_model |
| sync, t3k, tone3000, source | dual_database, job_processing, gear_model |
| process, render, audio, video | audio_processing, job_processing, signal_chain |

### Standard Patterns

| Keywords | Suggested Areas |
|----------|-----------------|
| form, submit, input, create, add | data_model, api_contract, security, frontend_layers |
| notification, alert, email | job_processing |
| upload, file, di track, recording | data_model, api_contract, security, job_processing |
| search, filter, browse, list | data_model, api_contract, frontend_layers |
| auth, login, oauth, session | security, data_model, api_contract |
| page, template, ui, display, show | frontend_layers, api_contract |

---

## Area Definitions

### GTS-Specific Areas

| ID | Name | Description | Key Questions |
|----|------|-------------|---------------|
| signal_chain | Signal Chain | Block types, ordering, validation rules | HEAD vs FULL_RIG, IR requirements, loop effects |
| gear_model | Gear Model | Unified gear, sources, sync records | Source attribution, GearModel files, UserGear |
| dual_database | Dual Database | gts_core vs gts_t3k_source boundaries | Which database, worker access, pgmq messages |
| frontend_layers | Frontend Layers | Astro SSG vs Jinja2 SSR vs HTMX fragments | Page type, React island, navigation patterns |
| job_processing | Jobs/Queues | TaskIQ jobs, pgmq consumers, parent/child | Retry strategy, progress reporting, Redis locks |
| audio_processing | Audio Processing | NAM, IR, loudness normalization | libs/audio vs apps/worker, processing pipeline |

### Standard Areas

| ID | Name | Description | Key Questions |
|----|------|-------------|---------------|
| data_model | Data Model | Tables, columns, relations (SQLAlchemy ORM) | Primary entity, lifecycle, indexes |
| orm_patterns | ORM Patterns | Repository pattern, transactions | Reference repository, eager/lazy loading |
| api_contract | API Contract | Endpoints, Pydantic schemas, errors | REST vs HTML endpoints, validation, pagination |
| security | Security | Auth, session cookies, ownership checks | Authentication required, CurrentUser, rate limiting |
| testing | Testing Strategy | Unit/integration/E2E boundaries, mock policy | What to test at each level, mock vs real |

---

## Detection Rules

**If feature mentions... Always include these areas:**

| Feature Mention | Required Areas |
|-----------------|----------------|
| Signal chain, block, amp, IR | signal_chain, gear_model |
| Processing, render, audio | audio_processing, job_processing |
| Sync, T3K, source | dual_database |
| Page, template, form | frontend_layers |
| Background, job, queue | job_processing |

---

## Presentation Format

Present areas as multi-select to user:

```
Based on GTS architecture, I've identified these areas to discuss:

[1] Data Model - Tables, columns, relations (SQLAlchemy ORM)
[2] Signal Chain - Block types, ordering, validation rules
[3] Gear Model - Unified gear, sources, sync records
[4] Dual Database - gts_core vs gts_t3k_source boundaries
[5] API Contract - Endpoints, Pydantic schemas, errors
[6] Jobs/Queues - TaskIQ jobs, pgmq consumers, parent/child
[7] Frontend Layers - Astro SSG vs Jinja2 SSR vs HTMX fragments
[8] Security - Auth, session cookies, ownership checks
[9] Testing - Unit/integration/E2E boundaries, mock policy

Select areas to discuss (comma-separated, or 'all'):
```

---

## Deep-Dive Templates

For each selected area, ask 3-5 targeted questions from the question bank. Capture answers as locked decisions in CONTEXT.md.
