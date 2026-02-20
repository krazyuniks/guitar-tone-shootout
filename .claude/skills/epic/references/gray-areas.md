# Area Detection Patterns

Keyword-based area detection for context assembly (Stage 2a). Used by `context_assembler.py` to determine which wiki sections and codebase files to include in CONTEXT.md.

## Area Definitions

Areas map to wiki content sources and codebase index files.

| ID | Name | Wiki Sections | Codebase Files |
|----|------|---------------|----------------|
| `data_model` | Data Model | domain-model, persistence, design-patterns | SCHEMA |
| `gear_model` | Gear Model | domain-model, api-design | SCHEMA, ENDPOINTS |
| `signal_chain` | Signal Chain | domain-model, api-design | SCHEMA, ENDPOINTS |
| `audio_processing` | Audio | audio, domain-model | IMPORTS |
| `frontend_layers` | Frontend | frontend | ENDPOINTS |
| `orm_patterns` | ORM Patterns | domain-model, persistence, design-patterns | SCHEMA |
| `api_contract` | API Contract | api-design, auth | ENDPOINTS |
| `job_processing` | Messaging & Workers | data-ingestion, infrastructure | IMPORTS |
| `dual_database` | Database | persistence, data-ingestion | SCHEMA, IMPORTS |
| `security` | Security | auth, api-design | ENDPOINTS |
| `testing` | Testing | testing | TESTS |

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
