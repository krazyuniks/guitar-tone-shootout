# /worktree-health - Check Worktree Health

Verify all services in the current worktree are healthy.

## Usage

```
/worktree-health
```

## Checks Performed

1. **Container status** - All 4 containers running
2. **Backend health** - `curl http://localhost:<port>/health`
3. **Database connectivity** - Backend can query DB
4. **Redis connectivity** - Backend can ping Redis
5. **Frontend serving** - Astro dev server responding

## Commands Executed

```bash
./worktree.py health
```

## Exit Codes

- `0` - All healthy
- `1` - One or more services unhealthy

## Example Output

```
✓ All services healthy
  Frontend: http://localhost:4321
  Backend:  http://localhost:8000
```

## Troubleshooting

If unhealthy, check:
```bash
docker compose ps          # Service status
docker compose logs -f     # Live logs
./worktree.py status       # Detailed status
```
