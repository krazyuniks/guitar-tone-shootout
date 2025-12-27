# /worktree-setup - Create New Worktree

Create a new git worktree with isolated Docker environment.

## Usage

```
/worktree-setup <issue-number|branch-name>
```

## Examples

```bash
/worktree-setup 42                    # From issue number
/worktree-setup 42/feature-audio      # Explicit branch name
/worktree-setup main                  # Register main worktree
```

## What Happens

1. **Parse input** - Issue number or branch name
2. **Generate branch** from GitHub issue title if needed
3. **Allocate resources** - Unique ports and volumes
4. **Create git worktree** at `../<branch-as-dirname>`
5. **Generate config files**:
   - `.env.local` - Worktree-specific environment
   - `docker-compose.override.yml` - Port/volume overrides
6. **Start Docker services**
7. **Seed database** from `../seed.sql`
8. **Run migrations**
9. **Verify health**

## Port Allocation

| Service | Main (offset 0) | Feature (offset N) |
|---------|-----------------|-------------------|
| Frontend | 4321 | 4321 + (N * 10) |
| Backend | 8000 | 8000 + (N * 10) |
| Database | 5432 | 5432 + N |
| Redis | 6379 | 6379 + N |

## Commands Executed

```bash
cd /path/to/main
./worktree.py setup <input>
```

## Post-Setup

After setup completes:
1. Navigate to new worktree: `cd ../<worktree-name>`
2. Verify services: `docker compose ps`
3. Check health: `./worktree.py health`
4. Open browser: `http://localhost:<frontend-port>`
