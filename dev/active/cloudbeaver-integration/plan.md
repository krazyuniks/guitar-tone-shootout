# Plan: Add CloudBeaver Database GUI to Docker Compose

**Issue:** #71
**Created:** 2025-12-27
**Status:** Ready to implement

## Summary
Add CloudBeaver (web-based DBeaver) as a Docker service that integrates with the worktree port isolation system. Each worktree will have its own CloudBeaver instance with unique ports.

## Port Allocation
Following the existing HTTP service pattern (10 offset multiplier):
| Worktree | Offset | CloudBeaver Port |
|----------|--------|------------------|
| main     | 0      | 8978             |
| feature-1| 1      | 8988             |
| feature-2| 2      | 8998             |

## Files to Modify

### 1. `docker-compose.yml` - Add CloudBeaver service
Add base CloudBeaver service definition with:
- `dbeaver/cloudbeaver:latest` image
- Volume for persistent workspace
- Dependency on `db` service
- Port defined in override file
- `profiles: [tools]` to make it optional

### 2. `worktree/config.py` - Add cloudbeaver port and volume
- Add `cloudbeaver: int` to `PortConfig` NamedTuple
- Add `cloudbeaver: str` to `VolumeConfig` NamedTuple
- Add `base_port_cloudbeaver: int = 8978` to Settings
- Update `calculate_ports()` to include cloudbeaver
- Update `calculate_volumes()` to include cloudbeaver workspace

### 3. `worktree/templates/docker-compose.override.yml.j2` - Add CloudBeaver override
Add CloudBeaver service with:
- Worktree-specific container name
- Port mapping to worktree-specific external port
- Worktree-specific volume name

### 4. `worktree/templates.py` - Update inline fallback
Update `_render_compose_override_inline()` to include CloudBeaver

### 5. Regenerate configs
Run `./worktree.py setup main` to regenerate with new CloudBeaver port

## CloudBeaver Service Configuration
```yaml
cloudbeaver:
  image: dbeaver/cloudbeaver:latest
  container_name: gts-{worktree}-cloudbeaver
  ports:
    - "127.0.0.1:{port}:8978"
  volumes:
    - {worktree}-cloudbeaver-workspace:/opt/cloudbeaver/workspace
  depends_on:
    db:
      condition: service_healthy
  environment:
    CB_SERVER_NAME: "GTS {worktree}"
  profiles:
    - tools
```

## Implementation Steps (in order)
1. Modify `worktree/config.py` - Add port and volume config
2. Modify `docker-compose.yml` - Add CloudBeaver service definition
3. Modify `worktree/templates/docker-compose.override.yml.j2` - Add override
4. Modify `worktree/templates.py` - Update inline fallback
5. Regenerate override for this worktree
6. Test: `docker compose --profile tools up -d cloudbeaver`
7. Browser test: Access http://localhost:8988 (this worktree's port)
8. Commit and create PR

## Usage After Implementation
1. Start services: `docker compose --profile tools up -d`
2. Access CloudBeaver: `http://localhost:8978` (or worktree-specific port)
3. First-time setup: Create admin user via web wizard
4. Add connection: PostgreSQL, host=`db`, port=`5432`, database=`shootout`, user=`shootout`

## Testing Strategy
1. Verify CloudBeaver container starts
2. Access web UI in browser
3. Create admin account
4. Add PostgreSQL connection
5. Browse tables and run queries
6. Take screenshot as proof
