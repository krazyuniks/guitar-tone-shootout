# Documentation Tests (T81)

These tests verify that project documentation has been updated to include the video BC.

## Running the Tests

**IMPORTANT:** These tests must run on the HOST, not in Docker containers, because the documentation files (AGENTS.md, DEVELOPMENT.md) are not mounted in the container filesystem.

```bash
# Run on HOST with uv
uv run pytest tests/unit/backend/documentation/ -v

# Or run specific test files
uv run pytest tests/unit/backend/documentation/test_development_md.py -v
uv run pytest tests/unit/backend/documentation/test_agents_md.py -v
uv run pytest tests/unit/backend/documentation/test_wiki_documentation.py -v
```

## Test Coverage

### test_development_md.py
Verifies DEVELOPMENT.md includes:
- ✓ Video in stack table (already present)
- ✗ libs/video/ in project structure tree (MISSING - needs implementation)
- ✗ src/video/ subdirectory layout (MISSING - needs implementation)
- ✓ Video in dependency rules (already present)
- ✓ No Cloudflare references (already correct)
- ✓ No stale contexts/video/ references (already correct)

### test_agents_md.py
Verifies AGENTS.md includes:
- ✓ Video in stack table (already present)
- ✗ libs/video/ in project structure tree (MISSING - needs implementation)
- ✓ Video in dependency rules (already present)
- ✓ No Cloudflare references (already correct)
- ✓ No stale contexts/video/ references (already correct)
- ✓ Structure trees consistent with DEVELOPMENT.md (already consistent)

### test_wiki_documentation.py
Documents requirements for wiki pages (manual verification):
- ✗ GTS-Technical-Architecture.md must mention video BC
- ✗ GTS-Remotion-Architecture.md issue numbers must be correct
- ✗ No stale contexts/video/ references in wiki
- ✗ No Cloudflare references in wiki

## Current Status

**9 tests passing** - Documentation already includes video in stack/dependency tables and has no stale references.

**7 tests failing** - Documentation missing:
1. libs/video/ in DEVELOPMENT.md project structure
2. libs/video/ in AGENTS.md project structure
3. src/video/ subdirectory layout in DEVELOPMENT.md
4. Wiki updates (4 manual verification tests)

## Implementation Notes

The implementer needs to:

1. Update DEVELOPMENT.md project structure tree to show libs/video/
2. Update DEVELOPMENT.md to show video BC subdirectory structure (src/video/composition, src/video/rendering, etc.)
3. Update AGENTS.md project structure tree to show libs/video/
4. Update wiki pages (or document why they're not in scope)

The stack tables and dependency rules already mention video processing, so those are complete.
