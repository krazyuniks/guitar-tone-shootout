# GTS-Specific Planning Context

## Feature Folder Derivation

### External State Mode (default)

State is stored at `~/.ralph/projects/{repo-name}/{branch}/`:

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
BRANCH=$(git branch --show-current)
REPO_NAME=$(basename "$(git remote get-url origin 2>/dev/null || echo "$PROJECT_ROOT")" .git)
FOLDER_NAME=$(echo "$BRANCH" | tr '/' '-')
STATE_DIR="$HOME/.ralph/projects/${REPO_NAME}/${FOLDER_NAME}"
```

**Examples:**
| Repo | Branch | State Directory |
|------|--------|-----------------|
| `ralph-hybrid` | `feature/42-auth` | `~/.ralph/projects/ralph-hybrid/feature-42-auth/` |
| `my-app` | `603-improve-display` | `~/.ralph/projects/my-app/603-improve-display/` |

### Legacy Mode (`--legacy` flag)

Folder name derived exactly from git branch name. Only transformation: slashes to dashes.

```bash
BRANCH=$(git branch --show-current)
FOLDER_NAME=$(echo "$BRANCH" | tr '/' '-')
FEATURE_DIR=".ralph-hybrid/${FOLDER_NAME}"
```

| Branch | Folder (CORRECT) | Folder (WRONG) |
|--------|------------------|----------------|
| `384/job-processing-pipeline-step-3-video-com` | `.ralph-hybrid/384-job-processing-pipeline-step-3-video-com/` | `.ralph-hybrid/384-video-composition/` |
| `feature/42-user-auth` | `.ralph-hybrid/feature-42-user-auth/` | `.ralph-hybrid/user-auth/` |

## SDLC Discovery for GTS

GTS uses `just` as its task runner. Expected commands:

```bash
just --list    # Discover available commands
```

Key commands:
- `just check` - Quality gates
- `just test-regression` - Stack tests
- `just test-unit` - Unit tests (Docker)
- `just test-integration` - Integration tests (Docker)
- `just test-e2e` - E2E tests (host)
- `just build-astro` - Build frontend

## SETTINGS Phase Defaults for GTS

```yaml
profile: balanced
max_iterations: 20
mcpServers:
  - chrome-devtools
  - playwright
successCriteria:
  command: "just test-regression"
  timeout: 300
healthCheck:
  command: "just up-d && sleep 5 && curl -f http://localhost:9000/health"
  timeout: 120
```

## Pattern Detection for GTS

| Pattern | GTS Indicators |
|---------|----------------|
| Frontend work | Mentions Jinja2, HTMX, Astro, Tailwind, templates |
| Backend work | Mentions FastAPI, SQLAlchemy, repositories, services |
| Dual-DB work | Mentions T3K, sync, worker, pgmq |
| Auth work | Mentions OAuth, session, login, T3K auth |
| Audio pipeline | Mentions NAM, IR, pedalboard, signal chain processing |

## TDD vs Validation for GTS

| Type | When | What | GTS Command |
|------|------|------|-------------|
| **TDD Tests** | During implementation | Tests Claude writes FIRST | `just tdd <path>` |
| **Validation** | After each story | Regression check | `just test-regression` |

## Story Sizing for GTS

GTS stories should consider:
- Container-first execution (all tests run in Docker)
- Pre-bundled Astro frontend (rebuild required for template changes)
- Dual database architecture (webapp vs T3K source)
- Port/adapter pattern (services, repositories, domain entities)

## Verify Criteria for GTS

GTS story verification should use `just` commands:

```json
{
  "verify": {
    "command": "just tdd tests/unit/webapp/test_feature.py",
    "expected": "All tests pass",
    "artifacts": ["apps/webapp/src/webapp/services/feature.py"],
    "wiring": ["Service registered in dependency injection"]
  }
}
```

## Final Status Output

### External State Mode

```
PLANNING COMPLETE (External State Mode)

Branch: {exact branch name}
State directory: ~/.ralph/projects/{repo-name}/{branch}/

Files:
  spec.md, prd.json, progress.log, PLAN-REVIEW.md

Ready to execute: ralph-hybrid run
```

### Legacy Mode

```
PLANNING COMPLETE

Branch: {exact branch name}
Feature folder: .ralph-hybrid/{branch}/

Files:
  spec.md, prd.json, progress.txt, PLAN-REVIEW.md

Ready to execute: ralph-hybrid run
```
