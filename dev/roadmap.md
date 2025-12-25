# Guitar Tone Shootout - Development Roadmap

## Phase 1: MVP (Current)

**Goal:** Validate technology stack with a simple end-to-end video

### Milestones

- [x] Project structure and tooling
- [x] INI config schema and parser
- [x] Audio processing module (NAM + Pedalboard)
- [x] Pipeline module (FFmpeg + Playwright)
- [x] Test suite (50 tests passing)
- [ ] Install Playwright browsers
- [ ] End-to-end test with real files
- [ ] CLI commands implementation
- [ ] Sample comparison video

### Acceptance Criteria

1. Process a single DI track through one NAM model + IR
2. Generate a comparison image from HTML template
3. Create a video clip combining image and audio
4. Output FLAC audio and MP4 video

---

## Phase 2: Full Pipeline

**Goal:** Complete multi-track, multi-amp comparison videos

### Milestones

- [ ] Multiple DI track support
- [ ] Permutation logic (cab outer, amp inner)
- [ ] Master video concatenation
- [ ] Silence trimming automation
- [ ] Progress reporting

---

## Phase 3: Web Interface

**Goal:** Flask + HTMX web UI for building comparisons

### Milestones

- [ ] Flask application structure
- [ ] pnpm + Tailwind + Flowbite setup
- [ ] Comparison builder UI
- [ ] File upload handling
- [ ] Job queue for async processing

---

## Phase 4: Community Features

**Goal:** Multi-user support and community features

### Milestones

- [ ] User authentication
- [ ] Database storage (SQLite → PostgreSQL)
- [ ] Comparison sharing
- [ ] Tone3000 integration
- [ ] Docker containerization

---

## Backlog

- AWS Lambda processing
- Commercial VST fallback via Reaper
- Tone matching algorithms
- A/B blind test mode
- YouTube API integration
