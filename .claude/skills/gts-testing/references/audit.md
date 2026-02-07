# Test Suite Audit

Comprehensive audit of the entire test suite to identify dead code, stub directories, naming issues, coverage gaps, and consolidation opportunities.

## Test Suite Structure

```
tests/
├── unit/
│   ├── backend/       # Fast unit tests (no DB/Redis)
│   ├── astro/         # Astro unit tests (currently empty)
│   └── worktree/      # Worktree CLI tests
├── integration/
│   └── backend/       # Integration tests (real services)
│       ├── pipeline/  # Audio/video pipeline tests
│       ├── migrations/
│       ├── websocket/
│       └── tasks/
├── e2e/
│   ├── python/        # E2E tests (pytest + Playwright, UI + DB verification)
│   └── smoke/         # Basic infrastructure smoke tests
└── data/              # Test fixtures and outputs
```

E2E tests use Python Playwright with direct database access for three-layer validation.

---

## Report Format

```markdown
# Test Suite Audit Report - [Date]

## Health Score: XX/100

## Critical (Fix Immediately)
- [ ] X broken testids (tests reference non-existent testids)
- [ ] X dead templates (not used by backend)
- [ ] X empty stub directories (remove or populate)

## High Priority (This Sprint)
- [ ] Consolidate X test file groups (duplicate coverage)
- [ ] X dead tests (target non-existent routes)

## Medium Priority (Backlog)
- [ ] X naming inconsistencies
- [ ] X tests missing error verification
- [ ] CI runs only X% of tests

## Metrics
| Metric | Current | Target |
|--------|---------|--------|
| E2E tests | X | Expand coverage |
| E2E quick tests | X | 20% of E2E |
| Unit tests | X | Maintain |
| Integration tests | X | Maintain |
| Empty stub dirs | X | 0 |
| Dead templates | X | 0 |
| Broken testids | X | 0 |
| CI coverage | X% | 20% |

## Detailed Findings
[By category with specific files and recommendations]
```

---

## Audit Checks

### 1. Empty Stub Directory Detection (HIGH)

Find test directories containing only `__init__.py` (no actual tests).

```bash
# Find directories with only __init__.py or conftest.py (no test files)
find tests -type d -not -path '*__pycache__*' -not -path '*.pytest*' \
  -not -path '*node_modules*' -not -path '*.venv*' -not -path '*allure*' \
  -not -path '*.ruff_cache*' | while read dir; do

  # Count test files
  test_count=$(find "$dir" -maxdepth 1 \( -name "test_*.py" -o -name "*.spec.ts" \) 2>/dev/null | wc -l)

  # Count total Python files
  py_count=$(find "$dir" -maxdepth 1 -name "*.py" -type f 2>/dev/null | wc -l)

  # If no tests but has __init__.py (stub directory)
  if [ "$test_count" -eq 0 ] && [ "$py_count" -le 2 ]; then
    init_exists=$(find "$dir" -maxdepth 1 -name "__init__.py" 2>/dev/null | wc -l)
    if [ "$init_exists" -eq 1 ]; then
      # Check if it has subdirectories with tests (parent directories are ok)
      subdir_tests=$(find "$dir" -mindepth 2 -name "test_*.py" 2>/dev/null | wc -l)
      if [ "$subdir_tests" -eq 0 ]; then
        echo "STUB: $dir"
      fi
    fi
  fi
done
```

**Known stub directories to verify:**
- `tests/e2e/admin/` - empty
- `tests/e2e/di_track/` - empty
- `tests/e2e/gear/` - empty
- `tests/e2e/shootout/` - empty
- `tests/e2e/signal_chain/` - empty
- `tests/unit/astro/` - empty
- `tests/integration/backend/tracing/` - empty
- `tests/integration/backend/repositories/` - empty
- `tests/integration/backend/workers/` - empty
- `tests/integration/services/` - empty

**Recommendation:** Either remove stub directories or document why they exist (planned tests).

**Score Impact:** -2 per stub directory (max -20)

### 2. Dead Template Detection (HIGH)

Find templates in `astro/dist/` not referenced by any backend route.

```bash
# Get all templates in dist/
find astro/dist/pages astro/dist/fragments -name "*.html" -type f | \
  sed 's|astro/dist/||' | sort > /tmp/all-templates.txt

# Get templates referenced in backend (name="..." pattern from TemplateResponse)
grep -roh 'name="[^"]*\.html"' apps/webapp/src/webapp/api/ --include="*.py" | \
  grep -oE '"[^"]+"' | tr -d '"' | sort -u > /tmp/used-templates.txt

# Find dead templates (in dist but not used)
comm -23 /tmp/all-templates.txt /tmp/used-templates.txt
```

**Score Impact:** -5 per dead template (max -25)

### 3. Broken TestId Detection (HIGH)

Find testids referenced in tests that don't exist in templates.

```bash
# Extract testids from Python E2E tests
grep -roh "get_by_test_id(['\"][^'\"]*['\"])\|locator.*data-testid.*['\"][^'\"]*['\"]" tests/e2e/python/tests/ --include="*.py" | \
  grep -oE "['\"][^'\"]+['\"]" | tr -d "'" | tr -d '"' | \
  sort -u > /tmp/test-testids.txt

# Extract testids from templates
grep -roh 'data-testid="[^"]*"' astro/dist/ --include="*.html" | \
  grep -oE '"[^"]+"' | tr -d '"' | sort -u > /tmp/template-testids.txt

# Find broken testids (in tests but not in templates)
comm -23 /tmp/test-testids.txt /tmp/template-testids.txt
```

**Score Impact:** -15 per broken testid (max -30)

### 4. Dead Test Detection (HIGH)

Find tests that target routes that don't exist in the backend.

```bash
# Extract page.goto URLs from Python tests
grep -roh "page\.goto.*['\"][^'\"]*['\"]" tests/e2e/python/tests/ --include="*.py" | \
  grep -oE "['\"][^'\"]+['\"]" | tr -d "'" | tr -d '"' | \
  grep -v 'http\|frontend_url' | sort -u > /tmp/test-routes.txt

# Get defined routes from backend
grep -roh "@router\.\(get\|post\|put\|delete\)(['\"][^'\"]*['\"]" apps/webapp/src/webapp/api/ --include="*.py" | \
  grep -oE "['\"][^'\"]+['\"]" | tr -d "'" | tr -d '"' | sort -u > /tmp/backend-routes.txt

# Compare (note: test routes may have variables like {id})
cat /tmp/test-routes.txt
```

Review test routes against backend routes. Tests targeting non-existent routes will silently fail.

**Score Impact:** -10 per dead test (max -20)

### 5. Duplicate Coverage Detection (MEDIUM)

Find multiple test files testing the same page.

```bash
# Group Python test files by primary page URL
for f in tests/e2e/python/tests/test_*.py; do
  primary_url=$(grep -m1 "page\.goto" "$f" 2>/dev/null | grep -oE "['\"][^'\"]+['\"]" | head -1 | tr -d "'\"")
  if [ -n "$primary_url" ]; then
    echo "$primary_url|$(basename $f)"
  fi
done | sort | awk -F'|' '{
  urls[$1] = urls[$1] ? urls[$1] ", " $2 : $2
  count[$1]++
}
END {
  for (url in count) {
    if (count[url] > 1) {
      print count[url] " files for " url ": " urls[url]
    }
  }
}'
```

**Score Impact:** -3 per duplicate pair (max -15)

### 6. Test Coverage Analysis (MEDIUM)

Count tests by category to identify coverage gaps.

```bash
# Unit tests
unit_tests=$(find tests/unit -name "test_*.py" -type f \
  -exec grep -h "def test_\|async def test_" {} \; 2>/dev/null | wc -l | tr -d ' ')

# Integration tests
integration_tests=$(find tests/integration -name "test_*.py" -type f \
  -exec grep -h "def test_\|async def test_" {} \; 2>/dev/null | wc -l | tr -d ' ')

# E2E tests
e2e_tests=$(find tests/e2e/python/tests -name "test_*.py" -type f \
  -exec grep -h "def test_\|async def test_" {} \; 2>/dev/null | wc -l | tr -d ' ')

# E2E quick tests
e2e_quick=$(grep -r "@pytest.mark.e2e_quick" tests/e2e/python/ --include="*.py" 2>/dev/null | wc -l | tr -d ' ')

# Smoke tests (pytest marker)
smoke_tests=$(grep -r "@pytest.mark.smoke" tests/ --include="*.py" 2>/dev/null | wc -l | tr -d ' ')

echo "Unit tests: $unit_tests"
echo "Integration tests: $integration_tests"
echo "E2E tests: $e2e_tests"
echo "E2E quick: $e2e_quick"
echo "Smoke-marked: $smoke_tests"
echo "Total: $((unit_tests + integration_tests + e2e_tests))"
```

**Score Impact:** Informational (no penalty)

### 7. Naming Analysis (MEDIUM)

Check for naming inconsistencies in testids and file names.

```bash
# Check testid naming patterns
grep -roh 'data-testid="[^"]*"' astro/dist/ --include="*.html" | \
  grep -oE '"[^"]+"' | tr -d '"' | sort -u | while read testid; do
  if echo "$testid" | grep -q "ditrack"; then
    echo "NAMING: '$testid' uses 'ditrack' (should be 'di-track')"
  fi
  if echo "$testid" | grep -q "signalchain"; then
    echo "NAMING: '$testid' uses 'signalchain' (should be 'signal-chain')"
  fi
done
```

**Known Issues:**

| Pattern | Issue | Examples |
|---------|-------|----------|
| `ditrack` vs `di-track` | Inconsistent hyphenation | testids, file names |
| `_` vs `-` | Mixed separators | Template vs testid names |

**Score Impact:** -2 per naming issue (max -10)

### 8. Error Verification Check (LOW)

Find E2E tests that don't verify browser errors.

```bash
for f in tests/e2e/python/tests/test_*.py; do
  has_console_check=$(grep -c "console.*error\|page\.on.*console" "$f" 2>/dev/null || echo 0)
  has_network_check=$(grep -c "requestfailed\|response.*status" "$f" 2>/dev/null || echo 0)

  if [ "$has_console_check" -eq 0 ] && [ "$has_network_check" -eq 0 ]; then
    echo "MISSING ERROR VERIFICATION: $(basename $f)"
  fi
done
```

**Recommended Pattern:**
```python
@pytest.fixture
async def page_with_error_check(page: Page):
    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    yield page
    assert not errors, f"Console errors: {errors}"
```

**Score Impact:** -1 per file missing verification (max -10)

### 9. CI Coverage Analysis (LOW)

Compare CI test coverage to total tests.

```bash
e2e_total=$(find tests/e2e/python/tests -name "test_*.py" -type f \
  -exec grep -h "async def test_\|def test_" {} \; 2>/dev/null | wc -l | tr -d ' ')

e2e_quick=$(grep -r "@pytest.mark.e2e_quick" tests/e2e/python/tests/ --include="*.py" 2>/dev/null | wc -l | tr -d ' ')

echo "E2E tests: $e2e_total total"
echo "E2E quick (CI): $e2e_quick"

if [ "$e2e_total" -gt 0 ]; then
  coverage=$((e2e_quick * 100 / e2e_total))
  echo "CI coverage: $coverage%"
fi
```

**Target:**
- CI should run at least 20% of E2E tests via `e2e_quick` marker
- E2E tests should cover all database-mutating operations

**Score Impact:** -5 if coverage < 10%, -2 if coverage < 20%

---

## Health Score Calculation

| Category | Max Penalty | Criteria |
|----------|-------------|----------|
| Empty stub dirs | -20 | -2 per directory (cap at 10) |
| Dead templates | -25 | -5 per template (cap at 5) |
| Dead tests | -20 | -10 per test (cap at 2) |
| Broken testids | -30 | -15 per testid (cap at 2) |
| Duplicate coverage | -15 | -3 per pair (cap at 5) |
| Naming issues | -10 | -2 per issue (cap at 5) |
| Error verification | -10 | -1 per E2E file (cap at 10) |
| CI coverage | -5 | -5 if <10%, -2 if <20% |

**Formula:** `Health Score = 100 + sum(penalties)`

**Score Interpretation:**
- **90-100:** Excellent -- minor cleanup only
- **70-89:** Good -- address high priority items
- **50-69:** Fair -- significant technical debt
- **0-49:** Poor -- major refactoring needed

---

## Quick Mode (--quick)

Only run critical checks (1-4):
- Empty stub directories
- Dead templates
- Broken testids
- Dead tests

---

## Create GitHub Issue (--create-issue)

Create a GitHub issue with the report:

```bash
gh issue create --repo krazyuniks/guitar-tone-shootout \
  --title "Test Suite Audit Report - $(date +%Y-%m-%d)" \
  --label "testing,maintenance,tech-debt" \
  --body "[Full report content]"
```

---

## Success Criteria

- [ ] Health score calculated
- [ ] All 9 checks executed (or 4 for quick mode)
- [ ] Empty stub directories identified
- [ ] Dead templates identified with file paths
- [ ] Broken testids identified with test file locations
- [ ] Duplicate coverage pairs listed with consolidation recommendations
- [ ] Backend test coverage counts provided
- [ ] Report generated in structured format
- [ ] Actionable items prioritised by severity
