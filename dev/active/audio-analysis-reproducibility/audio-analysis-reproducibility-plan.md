# Audio Analysis & Reproducibility - Plan

**Epic:** #58
**Milestone:** v2.8 - Audio Analysis & Reproducibility
**Created:** 2025-12-27

---

## Executive Summary

Add comprehensive audio analysis, AI evaluation, and full reproducibility metadata to Guitar Tone Shootout. This enables objective tonal comparison backed by numerical data, automatic AI-generated descriptions, and 100% reproducible processing.

---

## Goals

1. **Objective Metrics**: Capture 12+ audio metrics during processing
2. **AI Evaluation**: Generate human-readable tonal descriptions
3. **Full Reproducibility**: Store all processing parameters for exact recreation
4. **Precise Timestamps**: ms-accurate segment timing for deep linking

---

## Architecture

```
Pipeline Processing
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  Audio Metrics Extraction (pipeline/src/metrics.py)      │
│  - Core: RMS, Peak, Crest Factor, Dynamic Range          │
│  - Spectral: Centroid, Bass/Mid/Treble Energy            │
│  - Advanced: LUFS, Transient Density, Attack, Decay      │
└──────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  AI Evaluation Generator                                  │
│  - Algorithmic: Template-based from metric deviations     │
│  - LLM: Claude API for natural language (optional)        │
└──────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  Database (PostgreSQL JSONB)                              │
│  - Shootout: processing_metadata, normalization_settings  │
│  - Segment: audio_metrics, ai_evaluation, timestamps      │
└──────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  API Endpoints                                            │
│  - GET /shootouts/{id}/metadata                           │
│  - GET /shootouts/{id}/segments/{pos}/metrics             │
│  - GET /shootouts/{id}/comparison                         │
└──────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  Frontend Components                                      │
│  - Metrics Card with visual bars                          │
│  - AI Evaluation display                                  │
│  - Comparison chart (radar/spider)                        │
│  - Technical details accordion                            │
└──────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Metrics Foundation (#59, #60)
- Implement audio metrics extraction library
- Extend database schema with JSONB columns
- Create Pydantic models for serialization

### Phase 2: Metadata Capture (#62, #63)
- Add timestamp tracking during processing
- Capture all software versions and settings
- Compute file hashes for reproducibility

### Phase 3: AI Evaluation (#61)
- Implement algorithmic summary generator
- Integrate Claude API for LLM descriptions
- Compute standard deviations from averages

### Phase 4: API & Frontend (#64, #65)
- Add API endpoints for metrics/metadata
- Build frontend components for display
- Implement deep linking with timestamps

---

## Dependencies

- `numpy` - Core audio analysis
- `scipy` - Spectral analysis
- `pyloudnorm` - LUFS measurement
- `anthropic` - Claude API for LLM evaluation

---

## Risks

| Risk | Mitigation |
|------|------------|
| LLM costs | Make LLM evaluation optional, cache responses |
| Performance | Benchmark metrics extraction, target <100ms |
| Schema migration | Test migration on copy of production data |

---

## Success Criteria

- All 12+ metrics computed during processing
- AI evaluation generated for each segment
- Any shootout reproducible from stored metadata
- Timestamps accurate to 1ms
- Frontend displays all metrics and evaluations
