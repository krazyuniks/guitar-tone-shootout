# Audio Analysis & Reproducibility - Context

**Epic:** #58
**Last Updated:** 2025-12-27

---

## SESSION PROGRESS

### Current Status: Planning Complete

- [x] Epic created (#58)
- [x] Sub-issues created (#59-#65)
- [x] Dev-docs initialized
- [ ] Implementation not started

### Next Action
Begin with #59 (Audio metrics extraction library) in pipeline package.

---

## Key Decisions

### Metrics Selection
**Decision:** Comprehensive metrics (12+ measurements)
**Rationale:** User requested full analysis including LUFS, transient density, attack/sustain envelope

### AI Evaluation Approach
**Decision:** Algorithmic + LLM hybrid
**Rationale:** Algorithmic provides consistent, fast summaries; LLM adds natural language polish

### Storage Format
**Decision:** PostgreSQL JSONB
**Rationale:** Flexible schema, queryable, fits existing architecture

---

## Key Files

| File | Purpose |
|------|---------|
| `pipeline/src/metrics.py` | Audio metrics extraction (to be created) |
| `pipeline/src/evaluation.py` | AI evaluation generation (to be created) |
| `backend/app/models/segment.py` | Segment model with metrics columns |
| `backend/app/models/shootout.py` | Shootout model with metadata columns |
| `backend/app/api/shootouts.py` | API endpoints for metrics |
| `frontend/src/components/MetricsCard.tsx` | Metrics display component |

---

## Technical Constraints

1. **Performance**: Metrics extraction must complete in <100ms for 10s audio
2. **LLM Costs**: Claude API calls should be optional/cacheable
3. **Reproducibility**: SHA256 hashes required for all input files
4. **Timestamps**: Millisecond precision required for deep linking

---

## Research Notes

### Crest Factor Analysis
From POC testing (2025-12-27):
- 5153 + Bonsai: Peak -1.4 dB, RMS -14.0 dB → Crest 12.6 dB
- KDM MKIV: Peak -2.6 dB, RMS -14.0 dB → Crest 11.4 dB
- Higher crest factor = more transient punch

### Spectral Analysis Libraries
- `scipy.signal.spectrogram` - Basic spectral analysis
- `librosa` - More features but heavier dependency
- Recommendation: Start with scipy, add librosa if needed

---

## Quick Resume

```bash
# 1. Check current state
cat dev/active/audio-analysis-reproducibility/audio-analysis-reproducibility-context.md

# 2. View epic and sub-issues
gh issue view 58
gh issue list --milestone "v2.8 - Audio Analysis & Reproducibility"

# 3. Start implementation
git checkout -b 59-audio-metrics-library
```
