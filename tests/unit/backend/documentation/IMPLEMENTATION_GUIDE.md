# Implementation Guide for T81 Documentation Tests

This guide shows exactly what needs to be added to make the failing tests pass.

## Failing Tests Analysis

### 1. test_development_md.py::test_project_structure_shows_libs_video

**Current state:** DEVELOPMENT.md project structure doesn't show `libs/video/`

**Required fix:** Add `libs/video/` to the project structure tree in DEVELOPMENT.md

**Example addition:**
```
gts/
├── pyproject.toml
├── libs/
│   ├── core/                   # Domain (zero framework deps)
│   ├── audio/                  # Audio processing
│   └── video/                  # Video composition and rendering ← ADD THIS
│       └── src/video/
│           ├── composition/    # Video composition logic
│           ├── rendering/      # Remotion integration
│           └── models/         # Video-specific models
```

### 2. test_development_md.py::test_project_structure_shows_video_subdirectories

**Current state:** DEVELOPMENT.md doesn't show video BC internal structure

**Required fix:** Show the `src/video/` subdirectory structure (already partially covered by fix #1)

### 3. test_agents_md.py::test_project_structure_shows_libs_video

**Current state:** AGENTS.md project structure doesn't show `libs/video/`

**Required fix:** Add `libs/video/` to the project structure tree in AGENTS.md (same as DEVELOPMENT.md)

**Note:** Keep both structure trees consistent - they should match exactly.

### 4-7. Wiki Documentation Tests (Manual Verification)

**Current state:** Wiki pages are in a separate repository, cannot be automatically tested

**Required action:** Manual verification or update via GitHub wiki interface

**Wiki pages to check:**
1. `GTS-Technical-Architecture.md` - Add video BC to bounded context diagram
2. `GTS-Remotion-Architecture.md` - Verify all issue numbers reference valid GitHub issues
3. Both pages - Search for `contexts/video` and replace with `libs/video/`
4. Both pages - Verify no Cloudflare references exist

## What's Already Correct (9 passing tests)

✅ Stack tables already mention video (in the audio/processing context)
✅ Dependency rules already mention video
✅ No Cloudflare references exist in DEVELOPMENT.md or AGENTS.md
✅ No stale `contexts/video/` references exist
✅ DEVELOPMENT.md and AGENTS.md structure trees are consistent with each other

## Quick Implementation Checklist

- [ ] Update DEVELOPMENT.md project structure to include `libs/video/` with subdirs
- [ ] Update AGENTS.md project structure to include `libs/video/` with subdirs
- [ ] Verify both structure trees are identical
- [ ] Update wiki GTS-Technical-Architecture.md (or skip if out of scope)
- [ ] Update wiki GTS-Remotion-Architecture.md issue numbers (or skip if out of scope)
- [ ] Run tests: `uv run pytest tests/unit/backend/documentation/ -v`
- [ ] Verify all 16 tests pass (or 12 if wiki is out of scope)

## Expected Test Results After Implementation

If wiki is in scope:
```
16 passed
```

If wiki is out of scope (manual verification only):
```
12 passed, 4 failed (wiki manual verification tests)
```

The wiki tests will always fail because they use `pytest.fail()` to indicate manual verification is required. The implementer can either:
1. Update the wiki and remove the manual verification tests
2. Leave the wiki tests as-is (documenting the requirement without automating it)
3. Skip wiki tests with `@pytest.mark.skip` if wiki updates are deferred
