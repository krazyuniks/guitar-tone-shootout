"""Unit tests for T3K OAuth token management.

Tests verify Fernet encryption, token expiry checks, automatic refresh on 401,
and persistence to the OAuthToken staging table. External T3K OAuth API calls
use httpx MockTransport.
"""

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient, MockTransport, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from source_t3k.adapters.inbound.oauth import T3KOAuthManager
from source_t3k.adapters.outbound.models import Base, OAuthToken


@pytest.fixture
async def db_engine() -> AsyncEngine:
    """Create a test database engine for T3K staging tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncSession:
    """Create a test database session with transaction rollback."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture
def encryption_key() -> str:
    """Generate a Fernet encryption key for testing."""
    return Fernet.generate_key().decode()


def _make_oauth_manager(
    db_session: AsyncSession,
    encryption_key: str,
    handler=None,
) -> T3KOAuthManager:
    """Create a T3KOAuthManager with optional MockTransport handler."""
    manager = T3KOAuthManager(
        session=db_session,
        encryption_key=encryption_key,
        client_id="test-client-id",
        client_secret="test-client-secret",
        oauth_base_url="https://oauth.tone3000.com",
    )
    if handler is not None:
        manager._client = AsyncClient(transport=MockTransport(handler))
    return manager


class TestTokenEncryption:
    """Test Fernet encryption and decryption of OAuth tokens."""

    async def test_encrypts_access_token_at_rest(
        self, db_session: AsyncSession, encryption_key: str
    ) -> None:
        """Access tokens are encrypted using Fernet before persisting to DB."""
        manager = _make_oauth_manager(db_session, encryption_key)
        plaintext_token = "test-access-token-12345"
        encrypted = manager._encrypt(plaintext_token)

        # Encrypted value should be different from plaintext
        assert encrypted != plaintext_token

        # Decryption should recover original value
        fernet = Fernet(encryption_key.encode())
        decrypted = fernet.decrypt(encrypted.encode()).decode()
        assert decrypted == plaintext_token

    async def test_encrypts_refresh_token_at_rest(
        self, db_session: AsyncSession, encryption_key: str
    ) -> None:
        """Refresh tokens are encrypted using Fernet before persisting to DB."""
        manager = _make_oauth_manager(db_session, encryption_key)
        plaintext_token = "test-refresh-token-67890"
        encrypted = manager._encrypt(plaintext_token)

        # Encrypted value should be different from plaintext
        assert encrypted != plaintext_token

        # Decryption should recover original value
        fernet = Fernet(encryption_key.encode())
        decrypted = fernet.decrypt(encrypted.encode()).decode()
        assert decrypted == plaintext_token

    async def test_decrypts_access_token_from_database(
        self, db_session: AsyncSession, encryption_key: str
    ) -> None:
        """OAuthManager decrypts tokens when reading from database."""
        manager = _make_oauth_manager(db_session, encryption_key)
        plaintext_token = "test-access-token-abcde"
        encrypted_token = manager._encrypt(plaintext_token)

        # Store encrypted token in DB
        token_record = OAuthToken(
            id=1,
            access_token_encrypted=encrypted_token,
            refresh_token_encrypted=manager._encrypt("refresh-token"),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            created_at=datetime.now(UTC),
        )
        db_session.add(token_record)
        await db_session.commit()

        # Decrypt should recover plaintext
        decrypted = manager._decrypt(token_record.access_token_encrypted)
        assert decrypted == plaintext_token


class TestTokenExpiry:
    """Test token expiry checks and automatic refresh logic."""

    async def test_token_is_expired_when_past_expires_at(
        self, db_session: AsyncSession, encryption_key: str
    ) -> None:
        """Token is considered expired when current time > expires_at."""
        manager = _make_oauth_manager(db_session, encryption_key)
        token = OAuthToken(
            id=1,
            access_token_encrypted=manager._encrypt("token"),
            refresh_token_encrypted=manager._encrypt("refresh"),
            expires_at=datetime.now(UTC) - timedelta(minutes=5),  # 5 minutes ago
            created_at=datetime.now(UTC) - timedelta(hours=1),
        )
        db_session.add(token)
        await db_session.commit()

        assert manager._is_expired(token) is True

    async def test_token_is_not_expired_when_before_expires_at(
        self, db_session: AsyncSession, encryption_key: str
    ) -> None:
        """Token is not expired when current time < expires_at."""
        manager = _make_oauth_manager(db_session, encryption_key)
        token = OAuthToken(
            id=1,
            access_token_encrypted=manager._encrypt("token"),
            refresh_token_encrypted=manager._encrypt("refresh"),
            expires_at=datetime.now(UTC) + timedelta(hours=1),  # 1 hour from now
            created_at=datetime.now(UTC),
        )
        db_session.add(token)
        await db_session.commit()

        assert manager._is_expired(token) is False

    async def test_token_near_expiry_triggers_refresh(
        self, db_session: AsyncSession, encryption_key: str
    ) -> None:
        """Token is refreshed preemptively when within 5 minutes of expiry."""
        post_count = 0

        def handler(request: Request) -> Response:
            nonlocal post_count
            post_count += 1
            return Response(
                200,
                json={
                    "access_token": "new-access-token",
                    "refresh_token": "new-refresh-token",
                    "expires_in": 3600,
                },
            )

        manager = _make_oauth_manager(db_session, encryption_key, handler=handler)

        # Create a token expiring in 3 minutes
        token = OAuthToken(
            id=1,
            access_token_encrypted=manager._encrypt("old-token"),
            refresh_token_encrypted=manager._encrypt("refresh-token"),
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            created_at=datetime.now(UTC) - timedelta(hours=1),
        )
        db_session.add(token)
        await db_session.commit()

        # get_valid_token should refresh automatically
        valid_token = await manager.get_valid_token()
        assert valid_token == "new-access-token"

        # Verify refresh was called
        assert post_count == 1


class TestTokenRefresh:
    """Test OAuth token refresh flow."""

    async def test_refresh_token_calls_oauth_endpoint(
        self, db_session: AsyncSession, encryption_key: str
    ) -> None:
        """refresh_token() calls T3K OAuth endpoint with refresh_token grant."""
        captured_requests: list[Request] = []

        def handler(request: Request) -> Response:
            captured_requests.append(request)
            return Response(
                200,
                json={
                    "access_token": "new-access-token",
                    "refresh_token": "new-refresh-token",
                    "expires_in": 3600,
                },
            )

        manager = _make_oauth_manager(db_session, encryption_key, handler=handler)

        # Store existing token
        old_token = OAuthToken(
            id=1,
            access_token_encrypted=manager._encrypt("old-access"),
            refresh_token_encrypted=manager._encrypt("old-refresh"),
            expires_at=datetime.now(UTC) - timedelta(minutes=10),
            created_at=datetime.now(UTC) - timedelta(hours=2),
        )
        db_session.add(old_token)
        await db_session.commit()

        await manager.refresh_token()

        # Verify OAuth endpoint was called
        assert len(captured_requests) == 1
        assert "/token" in str(captured_requests[0].url)

    async def test_refresh_token_persists_new_tokens(
        self, db_session: AsyncSession, encryption_key: str
    ) -> None:
        """refresh_token() persists new tokens (encrypted) to database."""

        def handler(request: Request) -> Response:
            return Response(
                200,
                json={
                    "access_token": "refreshed-access-token",
                    "refresh_token": "refreshed-refresh-token",
                    "expires_in": 3600,
                },
            )

        manager = _make_oauth_manager(db_session, encryption_key, handler=handler)

        # Store existing token
        old_token = OAuthToken(
            id=1,
            access_token_encrypted=manager._encrypt("old-access"),
            refresh_token_encrypted=manager._encrypt("old-refresh"),
            expires_at=datetime.now(UTC) - timedelta(minutes=10),
            created_at=datetime.now(UTC) - timedelta(hours=2),
        )
        db_session.add(old_token)
        await db_session.commit()

        await manager.refresh_token()

        # Verify new tokens are persisted (encrypted)
        result = await db_session.execute(select(OAuthToken).where(OAuthToken.id == 1))
        updated_token = result.scalar_one()

        # Decrypt and verify
        decrypted_access = manager._decrypt(updated_token.access_token_encrypted)
        decrypted_refresh = manager._decrypt(updated_token.refresh_token_encrypted)

        assert decrypted_access == "refreshed-access-token"
        assert decrypted_refresh == "refreshed-refresh-token"

    async def test_refresh_token_updates_expires_at(
        self, db_session: AsyncSession, encryption_key: str
    ) -> None:
        """refresh_token() updates expires_at based on expires_in from OAuth response."""

        def handler(request: Request) -> Response:
            return Response(
                200,
                json={
                    "access_token": "new-token",
                    "refresh_token": "new-refresh",
                    "expires_in": 7200,
                },
            )

        manager = _make_oauth_manager(db_session, encryption_key, handler=handler)

        old_token = OAuthToken(
            id=1,
            access_token_encrypted=manager._encrypt("old-access"),
            refresh_token_encrypted=manager._encrypt("old-refresh"),
            expires_at=datetime.now(UTC) - timedelta(hours=1),
            created_at=datetime.now(UTC) - timedelta(hours=2),
        )
        db_session.add(old_token)
        await db_session.commit()

        before_refresh = datetime.now(UTC)

        await manager.refresh_token()

        # Verify expires_at is updated
        result = await db_session.execute(select(OAuthToken).where(OAuthToken.id == 1))
        updated_token = result.scalar_one()

        # Should be approximately 2 hours from now (within 10 seconds tolerance)
        expected_expiry = before_refresh + timedelta(seconds=7200)
        assert abs((updated_token.expires_at - expected_expiry).total_seconds()) < 10


class TestGetValidToken:
    """Test get_valid_token() method (main public API)."""

    async def test_get_valid_token_returns_decrypted_token_when_not_expired(
        self, db_session: AsyncSession, encryption_key: str
    ) -> None:
        """get_valid_token() returns decrypted access token when not expired."""
        manager = _make_oauth_manager(db_session, encryption_key)
        token = OAuthToken(
            id=1,
            access_token_encrypted=manager._encrypt("valid-access-token"),
            refresh_token_encrypted=manager._encrypt("refresh-token"),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            created_at=datetime.now(UTC),
        )
        db_session.add(token)
        await db_session.commit()

        valid_token = await manager.get_valid_token()
        assert valid_token == "valid-access-token"

    async def test_get_valid_token_refreshes_when_expired(
        self, db_session: AsyncSession, encryption_key: str
    ) -> None:
        """get_valid_token() automatically refreshes token when expired."""

        def handler(request: Request) -> Response:
            return Response(
                200,
                json={
                    "access_token": "refreshed-token",
                    "refresh_token": "new-refresh",
                    "expires_in": 3600,
                },
            )

        manager = _make_oauth_manager(db_session, encryption_key, handler=handler)

        expired_token = OAuthToken(
            id=1,
            access_token_encrypted=manager._encrypt("expired-token"),
            refresh_token_encrypted=manager._encrypt("refresh-token"),
            expires_at=datetime.now(UTC) - timedelta(minutes=30),
            created_at=datetime.now(UTC) - timedelta(hours=2),
        )
        db_session.add(expired_token)
        await db_session.commit()

        valid_token = await manager.get_valid_token()
        assert valid_token == "refreshed-token"

    async def test_get_valid_token_raises_when_no_token_in_database(
        self, db_session: AsyncSession, encryption_key: str
    ) -> None:
        """get_valid_token() raises exception when no token exists in database."""
        manager = _make_oauth_manager(db_session, encryption_key)
        with pytest.raises(RuntimeError, match="No OAuth token found"):
            await manager.get_valid_token()


class TestOAuthTokenModel:
    """Test OAuthToken staging model schema."""

    async def test_oauth_token_has_encrypted_access_token_field(
        self, db_session: AsyncSession, encryption_key: str
    ) -> None:
        """OAuthToken model has access_token_encrypted field."""
        fernet = Fernet(encryption_key.encode())
        encrypted = fernet.encrypt(b"test-access").decode()

        token = OAuthToken(
            id=1,
            access_token_encrypted=encrypted,
            refresh_token_encrypted=fernet.encrypt(b"test-refresh").decode(),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            created_at=datetime.now(UTC),
        )
        db_session.add(token)
        await db_session.commit()

        result = await db_session.execute(select(OAuthToken).where(OAuthToken.id == 1))
        saved = result.scalar_one()
        assert saved.access_token_encrypted == encrypted

    async def test_oauth_token_has_encrypted_refresh_token_field(
        self, db_session: AsyncSession, encryption_key: str
    ) -> None:
        """OAuthToken model has refresh_token_encrypted field."""
        fernet = Fernet(encryption_key.encode())
        encrypted = fernet.encrypt(b"test-refresh").decode()

        token = OAuthToken(
            id=1,
            access_token_encrypted=fernet.encrypt(b"test-access").decode(),
            refresh_token_encrypted=encrypted,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            created_at=datetime.now(UTC),
        )
        db_session.add(token)
        await db_session.commit()

        result = await db_session.execute(select(OAuthToken).where(OAuthToken.id == 1))
        saved = result.scalar_one()
        assert saved.refresh_token_encrypted == encrypted

    async def test_oauth_token_has_expires_at_field(
        self, db_session: AsyncSession, encryption_key: str
    ) -> None:
        """OAuthToken model has expires_at field."""
        fernet = Fernet(encryption_key.encode())
        expiry = datetime.now(UTC) + timedelta(hours=2)

        token = OAuthToken(
            id=1,
            access_token_encrypted=fernet.encrypt(b"test-access").decode(),
            refresh_token_encrypted=fernet.encrypt(b"test-refresh").decode(),
            expires_at=expiry,
            created_at=datetime.now(UTC),
        )
        db_session.add(token)
        await db_session.commit()

        result = await db_session.execute(select(OAuthToken).where(OAuthToken.id == 1))
        saved = result.scalar_one()
        # Compare with some tolerance for microseconds
        assert abs((saved.expires_at - expiry).total_seconds()) < 1

    async def test_oauth_token_has_created_at_field(
        self, db_session: AsyncSession, encryption_key: str
    ) -> None:
        """OAuthToken model has created_at field."""
        fernet = Fernet(encryption_key.encode())
        created = datetime.now(UTC)

        token = OAuthToken(
            id=1,
            access_token_encrypted=fernet.encrypt(b"test-access").decode(),
            refresh_token_encrypted=fernet.encrypt(b"test-refresh").decode(),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            created_at=created,
        )
        db_session.add(token)
        await db_session.commit()

        result = await db_session.execute(select(OAuthToken).where(OAuthToken.id == 1))
        saved = result.scalar_one()
        assert abs((saved.created_at - created).total_seconds()) < 1
