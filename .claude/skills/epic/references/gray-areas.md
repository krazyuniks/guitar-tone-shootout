# Gray Area Detection Patterns

Keyword-based area detection for filtering the question bank to relevant sections. Used by `context_assembler.py` to determine which wiki sections, codebase files, and question bank sections to present.

## Area Definitions

Areas map to sections in the question bank and to wiki/codebase content sources.

| ID | Name | Question Bank Section | Description |
|----|------|-----------------------|-------------|
| `data_model` | Data Model | 3. Domain Model | Entities, relationships, lifecycle |
| `gear_model` | Gear Model | 3. Domain Model / Gear Model | Unified gear, sources, sync records |
| `signal_chain` | Signal Chain | 3. Domain Model / Signal Chain | Block types, ordering, validation rules |
| `audio_processing` | Audio | 4. Libraries / Audio | NAM, IR, loudness normalisation |
| `frontend_layers` | Frontend | 5. Applications / Webapp / Frontend | Astro SSG, Jinja2 SSR, HTMX, React islands |
| `orm_patterns` | ORM Patterns | 5. Applications / Webapp / Persistence | Repository pattern, transactions |
| `api_contract` | API Contract | 5. Applications / Webapp / API | Endpoints, Pydantic schemas, errors |
| `job_processing` | Messaging & Workers | 2. Architecture / Messaging + 5. Applications / Workers | pgmq consumers, per-BC worker containers |
| `dual_database` | Database | 2. Architecture / Database | BC table isolation, pgmq queues |
| `security` | Security | 5. Applications / Webapp / Security | Auth, ownership checks |
| `testing` | Testing | 6. Testing Strategy | Unit/integration/E2E boundaries |

---

## Keyword Detection

### GTS Domain-Specific Patterns

| Keywords | Activated Areas |
|----------|-----------------|
| signal chain, chain, block, processing | signal_chain, audio_processing, gear_model |
| amp, pedal, ir, cabinet, capture, nam | gear_model, signal_chain, dual_database |
| shootout, compare, comparison, a/b | signal_chain, audio_processing, job_processing, frontend_layers |
| gear, library, collection, my gear | gear_model, frontend_layers, data_model |
| sync, t3k, tone3000, source | dual_database, job_processing, gear_model |
| process, render, audio, video | audio_processing, job_processing, signal_chain |

### Standard Patterns

| Keywords | Activated Areas |
|----------|-----------------|
| form, submit, input, create, add | data_model, api_contract, security, frontend_layers |
| notification, alert, email | job_processing |
| upload, file, di track, recording | data_model, api_contract, security, job_processing |
| search, filter, browse, list | data_model, api_contract, frontend_layers |
| auth, login, oauth, session | security, data_model, api_contract |
| page, template, ui, display, show | frontend_layers, api_contract |

---

## Required Area Rules

If the epic mentions these keywords, always include these areas regardless of other detection:

| Keywords | Required Areas |
|----------|----------------|
| signal chain, block, amp, IR | signal_chain, gear_model |
| processing, render, audio | audio_processing, job_processing |
| sync, T3K, source | dual_database |
| page, template, form | frontend_layers |
| background, job, queue | job_processing |

---

## Presentation

Present detected areas as multi-select for the human to confirm/adjust before questions are asked:

```
Detected areas (confirm or adjust):

[x] Data Model - Entities, relationships, lifecycle
[x] Gear Model - Unified gear, sources, sync records
[ ] Signal Chain - Block types, ordering, validation rules
[x] Frontend - Astro SSG, Jinja2 SSR, HTMX, React islands
[x] API Contract - Endpoints, Pydantic schemas, errors
[ ] Messaging & Workers - pgmq consumers, per-BC workers
[x] Security - Auth, ownership checks
[ ] Testing - Unit/integration/E2E boundaries
```

After confirmation, present only the matching question bank sections.
