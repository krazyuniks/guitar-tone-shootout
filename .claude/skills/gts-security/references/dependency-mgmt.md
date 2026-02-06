# Dependency Security Management

## Update Cadence

1. **Weekly:** Review dependabot PRs
2. **Monthly:** Run `pip-audit` and `npm audit`
3. **Before release:** Full security scan

## Version Pinning

- Pin exact versions in production (`==` for Python, exact in `package.json`)
- Use ranges only for development dependencies
- Lock files committed: `requirements.txt`, `pnpm-lock.yaml`

## Update Commands

```bash
# Update Python dependencies
docker compose exec webapp pip install --upgrade <package>
# Then update requirements.txt

# Update NPM dependencies
docker compose --profile build exec astro pnpm update <package>
```

## Secret Management

### Environment Variables

| Category | Location | Example |
|----------|----------|---------|
| **Development** | `.env` (gitignored) | `DB_PASSWORD=...` |
| **CI** | GitHub Secrets | Repository settings |
| **Production** | Platform secrets | Railway, Fly.io, etc. |

### Secret Categories

| Secret | Storage | Rotation |
|--------|---------|----------|
| Database password | Platform env | On breach |
| Session secret key | Platform env | On breach |
| T3K OAuth tokens | `.gts-auth.json` (600 perms) | Auto-refresh |

**Note:** T3K uses passwordless OAuth (email magic link). No client credentials stored.

### Auth File Security

The `.gts-auth.json` file stores OAuth tokens for development:
- Created with mode 0600 (owner read/write only)
- Permissions validated on every read
- Located in worktree parent directory (shared across worktrees)

```bash
# Verify permissions
ls -la $(dirname $(pwd))/.gts-auth.json
# Should show: -rw------- (600)
```
