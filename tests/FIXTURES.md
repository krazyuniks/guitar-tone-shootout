# Test Fixtures Reference

This document catalogues every shared pytest fixture used across the GTS test suite.

## Root Fixtures (`tests/conftest.py`)

These fixtures provide database connectivity and session isolation for all tests.

### `core_engine` (session-scoped)

Creates a single async SQLAlchemy engine for the entire test run. Syncs all ORM
table schemas (core + T3K) on startup.

- **Depends on:** `DATABASE_URL` environment variable
- **Creates:** `AsyncEngine` with `NullPool`

### `t3k_engine` (session-scoped)

Alias for `core_engine` — T3K tables are already synced during core engine setup.

### `core_connection` (function-scoped)

Opens a connection and begins an outer transaction. After the test, the transaction
is rolled back so all changes are discarded.

- **Depends on:** `core_engine`
- **Creates:** `AsyncConnection` with active outer transaction

### `db_session` (function-scoped)

The primary session fixture. Bound to `core_connection` with SAVEPOINT isolation:
when test code calls `session.commit()`, only the SAVEPOINT is committed. The
outer transaction is rolled back after the test.

- **Depends on:** `core_connection`
- **Creates:** `AsyncSession` (custom `_SavepointSession` subclass)

### `t3k_session` (function-scoped)

Alias for `db_session` in single-database mode.

### `session` (function-scoped)

Backwards-compatible alias for `db_session`.

---

## Unit Test Fixtures (`tests/unit/conftest.py`)

### `test_user`

Creates a single ORM `User` with a random suffix for uniqueness.

- **Depends on:** `session`
- **Creates:** `User` (ORM model)
- **Used by:** unit tests in `tests/unit/` that need a persisted user

---

## Integration Webapp Fixtures (`tests/integration/webapp/conftest.py`)

### Factory Fixtures

Factory fixtures return async callables. Call them to create instances with
sensible defaults; pass keyword arguments to override any field.

#### `make_user(db_session)`

Returns `async _make(**overrides) -> User`.

```python
user = await make_user()
admin = await make_user(username="admin", email="admin@example.com")
```

**Defaults:** random username/email suffix, `is_active=True`.

#### `make_di_track(db_session)`

Returns `async _make(user, **overrides) -> DITrack`.

```python
track = await make_di_track(test_user)
track = await make_di_track(test_user, name="Custom DI", sample_rate=96000)
```

**Defaults:** name="Test DI Track", file_path="/audio/test_di.wav",
duration_seconds=60.0, sample_rate=48000.

#### `make_shootout(db_session)`

Returns `async _make(user, di_track, *, chains=0, **overrides) -> Shootout`.

When `chains > 0`, creates that many `ShootoutChain` links, each referencing a
new empty `SignalChain`.

```python
shootout = await make_shootout(test_user, test_di_track)
shootout = await make_shootout(test_user, test_di_track, chains=3)
```

**Defaults:** name="Test Shootout".

#### `make_gear(db_session)`

Returns `async _make(gear_type, platform, *, models=1, **overrides) -> Gear`.

Creates the gear with a `GearSource`, a `GearTag`, and the specified number of
`GearModel` variants.

```python
gear = await make_gear(GearType.AMP, Platform.NAM)
gear = await make_gear(GearType.PEDAL, Platform.NAM, models=3)
```

**Defaults:** gear_type=AMP, platform=NAM, models=1, is_public=True.

#### `make_signal_chain(db_session)`

Returns `async _make(user, *, blocks=[], **overrides) -> SignalChain`.

Each entry in `blocks` is a dict of column overrides for `SignalChainBlock`.

```python
chain = await make_signal_chain(test_user)
chain = await make_signal_chain(
    test_user,
    blocks=[{"gear_type": GearType.FULL_RIG}],
)
```

**Defaults:** name="Test Signal Chain", platform=NAM.

#### `make_user_gear(db_session)`

Returns `async _make_user_gear(user_id, gear_model_id) -> UserGear`.

Legacy factory for creating UserGear junction records.

### Singleton Fixtures

These create one canonical instance per test, using the factory fixtures
internally. Most integration tests should use these.

| Fixture | Creates | Key details |
|---------|---------|-------------|
| `test_user` | `User` | Random suffix username/email |
| `test_di_track` | `DITrack` | Owned by `test_user`, 60s @ 48 kHz |
| `test_gear` | `Gear` | AMP/NAM with source, tag, 1 model |
| `test_shootout` | `Shootout` | 2 chains, owned by `test_user` |
| `test_signal_chain` | `SignalChain` | 1 FULL_RIG block, owned by `test_user` |

### Authenticated Client

#### `authenticated_client`

HTTPX `AsyncClient` with auth wired for `test_user`. Uses the main webapp from
`webapp.main.app`.

- **Depends on:** `db_session`, `test_user`
- **Creates:** `AsyncClient` (as async generator)

```python
async def test_page_renders(authenticated_client):
    resp = await authenticated_client.get("/library/shootouts")
    assert resp.status_code == 200
```

**Note:** Tests that need a custom `app` (e.g., mounting only specific routers)
define their own local `authenticated_client` fixture.

### Data Seeding

#### `seeded_db_session`

Returns the same `db_session` after seeding two gear items (Mesa Boogie Mark V,
Fender Twin Reverb) with tags, sources, and models. Used by gear page tests.

### Auto-Use Fixtures

#### `_wire_auth_session` (autouse)

Sets `db_session` as the session override, configures upload directory to
`tmp_path`, and sets the HMAC secret key to "test-secret". Cleans up after yield.

### Hooks

#### `pytest_runtest_call`

Automatically wires `test_user` as the current authenticated user when:
- `test_user` is a direct parameter of the test function, OR
- `authenticated_client` is a direct parameter

Does NOT wire if `unauthenticated_client` is also a direct parameter.

---

## Scheduler Fixtures (`tests/unit/scheduler/conftest.py`)

### `_register_test_session` (autouse)

Injects the test session into `t3k_sync.tasks` for SAVEPOINT isolation in
scheduler unit tests.

---

## Regression Fixtures (`tests/regression/conftest.py`)

Empty — regression tests use root conftest fixtures directly.
