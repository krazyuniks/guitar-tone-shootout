# Audio Analysis & Reproducibility - Tasks

**Epic:** #58
**Last Updated:** 2025-12-27

---

## Phase 1: Metrics Foundation

### #59 - Audio Metrics Extraction Library
- [ ] Create `pipeline/src/metrics.py`
- [ ] Implement core metrics (RMS, Peak, Crest Factor, Dynamic Range)
- [ ] Implement spectral metrics (Centroid, Bass/Mid/Treble Energy)
- [ ] Implement advanced metrics (LUFS, Transient Density, Attack, Decay)
- [ ] Create Pydantic models for metrics
- [ ] Add unit tests
- [ ] Benchmark performance (<100ms target)

### #60 - Database Schema
- [ ] Add `processing_metadata` JSONB to Shootout model
- [ ] Add `normalization_settings` JSONB to Shootout model
- [ ] Add `audio_metrics` JSONB to Segment model
- [ ] Add `pre_normalization_metrics` JSONB to Segment model
- [ ] Add `signal_chain_metadata` JSONB to Segment model
- [ ] Add `ai_evaluation` JSONB to Segment model
- [ ] Add timestamp columns (start_ms, end_ms, duration_ms)
- [ ] Create Alembic migration
- [ ] Update Pydantic schemas
- [ ] Test migration

---

## Phase 2: Metadata Capture

### #62 - Segment Timestamp Tracking
- [ ] Track cumulative position during audio concatenation
- [ ] Store timestamps in segment record
- [ ] Ensure audio/video timestamp alignment
- [ ] Add `?t=` parameter support to frontend
- [ ] Test timestamp accuracy (1ms tolerance)

### #63 - Shootout Metadata Capture
- [ ] Capture software versions (pedalboard, NAM, ffmpeg, pipeline)
- [ ] Capture audio settings (sample_rate, bit_depth)
- [ ] Capture normalization settings
- [ ] Compute SHA256 hashes for DI, NAM model, IR
- [ ] Capture NAM plugin settings from preset
- [ ] Store in shootout record
- [ ] Add reproducibility test

---

## Phase 3: AI Evaluation

### #61 - AI Evaluation Generation
- [ ] Implement algorithmic summary generator
  - [ ] Crest factor interpretation
  - [ ] Spectral centroid interpretation
  - [ ] Dynamic range interpretation
  - [ ] Bass/Mid/Treble balance interpretation
- [ ] Integrate Claude API for LLM descriptions
- [ ] Implement caching for LLM responses
- [ ] Compute standard deviations from shootout averages
- [ ] Add unit tests for algorithmic rules
- [ ] Add integration tests with mock LLM

---

## Phase 4: API & Frontend

### #64 - API Endpoints
- [ ] GET /shootouts/{id}/metadata
- [ ] GET /shootouts/{id}/segments/{pos}/metrics
- [ ] GET /shootouts/{id}/comparison
- [ ] Add Pydantic response schemas
- [ ] Add OpenAPI documentation
- [ ] Add unit tests
- [ ] Handle 404 for missing segments

### #65 - Frontend Display
- [ ] Metrics Card component with visual bars
- [ ] AI Evaluation display with loading state
- [ ] Comparison radar/spider chart
- [ ] Deviations table
- [ ] Technical details accordion
- [ ] Deep link support with timestamp seeking
- [ ] Mobile responsive design
- [ ] Choose chart library (Recharts vs visx)

---

## Acceptance Criteria

- [ ] All 12+ metrics computed during pipeline processing
- [ ] Metrics stored in PostgreSQL JSONB columns
- [ ] AI evaluation generated for each segment
- [ ] Standard deviation from shootout average computed
- [ ] All processing metadata captured (versions, normalization, etc.)
- [ ] Segment timestamps accurate to millisecond
- [ ] API returns full reproducibility metadata
- [ ] Frontend displays metrics and AI evaluation
- [ ] Any shootout reproducible from stored metadata
