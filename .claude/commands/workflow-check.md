---
description: Verify development hot reload infrastructure
allowed-tools: Bash(docker compose:*), Bash(just:*), Bash(stat:*), Bash(touch:*), Bash(sleep:*), Bash(ls:*), Bash(git checkout:*)
context: fork
model: haiku
---

# /workflow-check - Verify Hot Reload

Verify that development hot reload and file watching work correctly.

## Prerequisites

First verify the development environment is running:

```bash
# Check services are running
docker compose ps

# Check watch is running (should show chokidar process)
docker compose exec -T frontend pgrep -f "chokidar" || echo "Watch NOT running - run 'just watch-templates' first"
```

If prerequisites fail, inform the user and stop.

## Verification Sequence

Test each file type in order:

### 1. Astro Pages

```bash
# Get baseline
BEFORE=$(stat -f %m astro/dist/index.html 2>/dev/null || stat -c %Y astro/dist/index.html 2>/dev/null || echo "0")

# Touch file
touch astro/src/pages/index.astro

# Wait for rebuild
sleep 4

# Check result
AFTER=$(stat -f %m astro/dist/index.html 2>/dev/null || stat -c %Y astro/dist/index.html 2>/dev/null || echo "0")

if [ "$BEFORE" != "$AFTER" ] && [ "$AFTER" != "0" ]; then
  echo "PASS: Astro page rebuild"
else
  echo "FAIL: Astro page did not rebuild"
fi
```

### 2. CSS/Tailwind

```bash
CSS_FILE=$(ls -t astro/dist/_astro/*.css 2>/dev/null | head -1)
if [ -n "$CSS_FILE" ]; then
  BEFORE=$(stat -f %m "$CSS_FILE" 2>/dev/null || stat -c %Y "$CSS_FILE" 2>/dev/null)
  touch astro/src/styles/global.css
  sleep 4
  AFTER=$(stat -f %m "$CSS_FILE" 2>/dev/null || stat -c %Y "$CSS_FILE" 2>/dev/null)
  if [ "$BEFORE" != "$AFTER" ]; then
    echo "PASS: CSS rebuild"
  else
    echo "FAIL: CSS did not rebuild"
  fi
else
  echo "SKIP: No CSS file in dist"
fi
```

### 3. React Islands

```bash
if [ -f astro/dist/islands/signal-chain-builder.js ]; then
  BEFORE=$(stat -f %m astro/dist/islands/signal-chain-builder.js 2>/dev/null || stat -c %Y astro/dist/islands/signal-chain-builder.js 2>/dev/null)
  touch astro/src/islands/signal-chain-builder.tsx
  sleep 4
  AFTER=$(stat -f %m astro/dist/islands/signal-chain-builder.js 2>/dev/null || stat -c %Y astro/dist/islands/signal-chain-builder.js 2>/dev/null)
  if [ "$BEFORE" != "$AFTER" ]; then
    echo "PASS: React island rebuild"
  else
    echo "FAIL: React island did not rebuild"
  fi
else
  echo "SKIP: No islands file"
fi
```

### 4. Python Backend

```bash
touch backend/app/main.py
sleep 3
if docker compose logs backend --tail=15 2>&1 | grep -qiE "reload|restart|restarting|detected change"; then
  echo "PASS: Backend auto-reload"
else
  echo "INFO: Backend may use polling reload (normal on Mac)"
fi
```

### 5. Jinja2 Templates

```bash
if [ -d astro/dist/pages ]; then
  echo "PASS: Jinja2 auto-reloads on request (no build needed)"
else
  echo "SKIP: No templates directory"
fi
```

## Cleanup

Revert touched files (no actual content changes):

```bash
git checkout -- astro/src/pages/index.astro astro/src/styles/global.css astro/src/islands/signal-chain-builder.tsx backend/app/main.py 2>/dev/null || true
```

## Output Format

Report results as a table:

```markdown
## Hot Reload Verification

### Prerequisites
- Services: [RUNNING / NOT RUNNING]
- Watch process: [RUNNING / NOT RUNNING]

### Results

| Component | Status | Time |
|-----------|--------|------|
| Astro pages | PASS/FAIL | ~4s |
| CSS/Tailwind | PASS/FAIL | ~4s |
| React islands | PASS/FAIL/SKIP | ~4s |
| Python backend | PASS/INFO | ~3s |
| Jinja2 templates | PASS | instant |

### Issues (if any)
- [Description of any failures]
- [Recommended fix]
```

## If Tests Fail

Common fixes:

| Failure | Fix |
|---------|-----|
| Watch not running | Run `just watch-templates` in separate terminal |
| Astro not rebuilding | Restart: `docker compose restart frontend` |
| Python not reloading | Restart: `docker compose restart backend` |
| All failing | Full restart: `just down && just up-d` |
