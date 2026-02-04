# Mutation Verification Skill

Verify that UI mutations (POST/PUT/DELETE) persist to database.

## Problem

UI operations may appear to succeed but fail to persist:
- Success toast shows, but data not saved
- Form submits, but entity not created
- Delete button works, but record still exists
- 409 conflicts not visible in UI

## When to Use

- After any form submission
- After any "Save", "Delete", "Update" button click
- When testing CRUD operations
- After any mutation that should change database state

## Three-Layer Verification

### Layer 1: UI Response

Check visual feedback:
- Success toast/message appears
- No error displayed
- Expected redirect or state change

```
mcp__chrome-devtools__screenshot
```

### Layer 2: API Response

Check network tab for the mutation request:

```
mcp__chrome-devtools__get_network_logs
```

**Verify:**
- 2xx status code (200, 201, 204)
- Response body contains expected data
- No error messages in response

**Watch for:**
- 409 Conflict (unique constraint violation)
- 422 Validation Error (bad input)
- 500 Internal Server Error (backend crash)

### Layer 3: Database State

Query database directly to verify persistence:

```bash
docker compose exec -T webapp python -c "
import asyncio
from sqlalchemy import select
from app.core.database import async_session_factory
from app.models import YourModel  # Replace with actual model

async def check():
    async with async_session_factory() as session:
        result = await session.execute(
            select(YourModel).where(YourModel.id == 'your-id')
        )
        row = result.scalar_one_or_none()
        if row:
            print('FOUND:', row.id, row.name)
        else:
            print('NOT FOUND')

asyncio.run(check())
"
```

## Common Models

| Entity | Model | Key Field |
|--------|-------|-----------|
| Gear Pack | `GearPack` | `id`, `name`, `slug` |
| Shootout | `Shootout` | `id`, `name`, `user_id` |
| Signal Chain | `SignalChain` | `id`, `name` |
| User Gear | `UserGear` | `id`, `user_id`, `gear_pack_id` |

## Query Examples

### Check if gear pack exists

```bash
docker compose exec -T webapp python -c "
import asyncio
from sqlalchemy import select
from app.core.database import async_session_factory
from app.models import GearPack

async def check():
    async with async_session_factory() as session:
        result = await session.execute(
            select(GearPack).where(GearPack.slug == 'your-slug')
        )
        row = result.scalar_one_or_none()
        print('FOUND' if row else 'NOT_FOUND', row and row.name)

asyncio.run(check())
"
```

### Check if user gear was saved

```bash
docker compose exec -T webapp python -c "
import asyncio
from sqlalchemy import select
from app.core.database import async_session_factory
from app.models import UserGear

async def check():
    async with async_session_factory() as session:
        result = await session.execute(
            select(UserGear).where(
                UserGear.user_id == 'user-uuid',
                UserGear.gear_pack_id == 'pack-uuid'
            )
        )
        row = result.scalar_one_or_none()
        print('FOUND' if row else 'NOT_FOUND')

asyncio.run(check())
"
```

### List recent entries

```bash
docker compose exec -T webapp python -c "
import asyncio
from sqlalchemy import select
from app.core.database import async_session_factory
from app.models import Shootout

async def check():
    async with async_session_factory() as session:
        result = await session.execute(
            select(Shootout).order_by(Shootout.created_at.desc()).limit(5)
        )
        for row in result.scalars():
            print(f'{row.id}: {row.name}')

asyncio.run(check())
"
```

## Common Failure Patterns

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| UI shows success, DB empty | Transaction not committed | Add `await session.commit()` |
| 409 Conflict | Unique constraint violation | Check for existing record |
| 500 Error | Missing foreign key | Verify related entity exists |
| Stale data after refresh | Cache not invalidated | Clear/update cache after mutation |
| Optimistic update reverted | Server rejected change | Check API response for errors |

## Verification Flow

```
1. Perform UI mutation
    ↓
2. Check UI feedback (success message?)
    ↓
3. Check network tab (2xx status?)
    ↓
4. Query database (data persisted?)
    ↓
5. If any layer fails → INVESTIGATE
    ↓
6. All layers pass → Mutation verified
```

## Integration with Testing

For CRUD features, write Playwright tests that:
1. Perform the UI action
2. Verify success indication
3. Refresh page
4. Verify data still present

```typescript
// Example: Create and verify
await page.getByRole('button', { name: 'Save' }).click();
await expect(page.getByText('Saved successfully')).toBeVisible();
await page.reload();
await expect(page.getByTestId('item-name')).toContainText('My Item');
```

## Quick Reference

```bash
# Check any model by ID
docker compose exec -T webapp python -c "
from app.models import MODEL_NAME
# ... query code
"

# See recent Docker logs for errors
docker compose logs backend --tail=50 | grep -E 'ERROR|Exception'

# Check network tab via MCP
mcp__chrome-devtools__get_network_logs
```
