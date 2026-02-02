---
name: gts-testing
description: Test development with pytest, fixtures, and integration testing. Use for writing tests, test patterns, parametrization, and debugging test failures. GTS-specific patterns.
context: fork
---

# Testing Skill

Quick reference for writing tests. For full methodology and philosophy, see [Testing Methodology](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Testing-Methodology) in the wiki.

**Philosophy:** Test real services, mock only external network APIs. See `.claude/rules/testing-policy.md`.

## Test Type Taxonomy

| Test Type | What It Tests | Location |
|-----------|---------------|----------|
| **Unit Tests** | Single function/class in isolation | `tests/unit/backend/` |
| **Backend-Integration Tests** | Service orchestration, real DB/Redis | `tests/integration/backend/` |
| **E2E Tests** | Browser + DB verification | `tests/e2e/python/` |
| **Smoke Tests** | Critical path quick validation | Marker-based (`-m smoke`) |

## Test Marker Decision Tree

Use this to choose the right marker for your test:

```
Is it a browser-based test?
├── YES: Mark with @pytest.mark.e2e
│   ├── Fast critical path? → Also add @pytest.mark.e2e_quick + @pytest.mark.smoke
│   └── Full workflow?      → Also add @pytest.mark.e2e_full
└── NO: Does it need real DB/Redis?
    ├── YES: Place in tests/integration/ (auto-marked @pytest.mark.integration)
    │   └── Critical for CI? → Also add @pytest.mark.smoke
    └── NO: Place in tests/unit/ (auto-marked @pytest.mark.unit)
        └── Critical for CI? → Also add @pytest.mark.smoke
```

## Test Structure

```
tests/
├── conftest.py              # Root config: markers, pytest_plugins
├── fixtures/                # Shared fixtures
│   ├── database.py          # DB session with transaction rollback
│   ├── auth.py              # JWT tokens, auth headers
│   └── factories.py         # Test data factories
├── unit/backend/            # Pure logic, no external deps
├── integration/backend/     # Real DB/Redis tests
└── e2e/
    ├── python/              # E2E tests (pytest + Playwright)
    │   ├── conftest.py      # Browser fixtures, auth, DB access
    │   └── tests/           # Test files
    └── smoke/               # Infrastructure smoke tests
```

## Key Fixtures

### Database Session (Transaction Rollback)

```python
@pytest.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Real database with transaction rollback."""
    connection = await db_engine.connect()
    transaction = await connection.begin()

    async_session_factory = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    session = async_session_factory()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()
```

### Factory Fixture Pattern

```python
@pytest.fixture(scope="function")
def make_signal_chain(db_session: AsyncSession, test_user):
    """Factory for creating signal chains."""
    async def _make_signal_chain(name: str = "Test Chain", **kwargs):
        chain = SignalChain(
            id=uuid4(),
            user_id=test_user.id,
            name=name,
            **kwargs,
        )
        db_session.add(chain)
        await db_session.flush()
        await db_session.refresh(chain)
        return chain

    return _make_signal_chain
```

### Authentication

```python
@pytest.fixture(scope="function")
def auth_headers(auth_token: str) -> dict[str, str]:
    """Authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}"}
```

## Test Patterns

### Backend-Integration Test (Preferred)

```python
@pytest.mark.asyncio
async def test_create_signal_chain(client, auth_headers, test_user):
    """Test creating a signal chain via API."""
    response = await client.post(
        "/api/v1/signal-chains",
        json={"name": "Test Chain", "platform": "nam"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["name"] == "Test Chain"
```

### Unit Test (Pure Logic)

```python
def test_signal_chain_validates_name():
    """Test domain validation without database."""
    with pytest.raises(ValueError, match="Name cannot be empty"):
        SignalChainCreate(name="", platform="nam")
```

### E2E Test (Python Playwright)

```python
@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.e2e_quick
async def test_creates_signal_chain(page: Page, db_session, frontend_url: str):
    """Three-layer validation: UI action → DOM update → database state."""

    # LAYER 1: UI Action - Navigate and interact
    await page.goto(f"{frontend_url}/builder")
    await page.fill('[name="chain-name"]', 'My Chain')
    await page.click('button:has-text("Save")')

    # LAYER 2: DOM Update - Verify UI response
    await expect(page.locator('[data-testid="chain-card"]')).to_be_visible()

    # LAYER 3: Database State - Verify persistence
    result = await db_session.execute(
        text("SELECT id FROM signal_chains WHERE name = :name"),
        {"name": "My Chain"}
    )
    assert result.fetchone() is not None
```

### Mocking External APIs Only

```python
@pytest.mark.asyncio
async def test_t3k_sync_handles_error(db_session, test_user):
    """Mock EXTERNAL API only - never mock internal services."""
    with patch("app.services.t3k_client.fetch_tones") as mock:
        mock.side_effect = ExternalAPIError("T3K down")
        service = T3KSyncService(db_session)
        result = await service.sync_user_tones(test_user.id)
        assert result.status == "failed"
```

## Pytest Markers Reference

| Marker | Use When | Runtime | Auto-Applied |
|--------|----------|---------|--------------|
| `smoke` | Critical path, must pass for CI | < 3 min | `tests/e2e/smoke/` |
| `unit` | Testing single function/class | < 1 sec | `tests/unit/` |
| `integration` | Testing with real DB/Redis | < 10 sec | `tests/integration/` |
| `e2e` | Browser-based tests | varies | `tests/e2e/` |
| `e2e_quick` | Fast E2E for commit validation | < 1 min | Manual |
| `e2e_full` | Comprehensive E2E for PR | < 10 min | Manual |
| `t3k_integration` | Real Tone3000 API (skip in CI) | varies | Manual |
| `docker_only` | Requires container volume mounts | varies | Manual |
| `slow` | Tests > 10 seconds (reserved) | > 10 sec | Manual |

## Common Fixtures Quick Reference

### Integration Tests

| Fixture | Description | Scope |
|---------|-------------|-------|
| `db_session` | Async DB session with transaction rollback | function |
| `test_user` | Authenticated test user | function |
| `other_user` | Second user for isolation tests | function |
| `client` | httpx AsyncClient (unauthenticated) | function |
| `authenticated_client` | httpx AsyncClient with auth headers | function |
| `auth_headers` | `{"Authorization": "Bearer ..."}` dict | function |
| `make_signal_chain` | Factory for SignalChain objects | function |
| `make_user_gear` | Factory for UserGear objects | function |
| `make_di_track` | Factory for DITrack objects | function |
| `make_shootout` | Factory for Shootout objects | function |

### E2E Tests

| Fixture | Description | Scope |
|---------|-------------|-------|
| `page` | Authenticated Playwright page | function |
| `guest_page` | Unauthenticated Playwright page | function |
| `frontend_url` | Base URL (e.g., `http://localhost:9000`) | session |
| `backend_url` | API URL (e.g., `http://localhost:8000`) | session |
| `db_session` | Direct DB access for verification | function |
| `current_user_id` | Authenticated user's UUID | function |
| `auth_client` | Context manager for authenticated API calls | function |
| `test_wav_file` | Path to test WAV file | session |
| `uploaded_di_track` | Pre-uploaded DI track for testing | function |

## Related

- [Testing Methodology](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Testing-Methodology) - Full methodology (GitHub Wiki)
- `.claude/rules/testing-policy.md` - Testing rules
- `.claude/rules/testing-policy.md` - Claude's testing role
- `tests/AGENTS.md` - Test structure and placement guide
- `tests/conftest.py` - Full marker documentation and decision tree
