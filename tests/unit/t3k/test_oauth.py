"""Unit tests for T3K OAuth token management.

Tests verify Fernet encryption, token expiry checks, automatic refresh on 401,
and persistence to the OAuthToken staging table. External T3K OAuth API calls
are mocked per testing policy.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient, Request, Response
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


@pytest.fixture
def mock_httpx_client() -> AsyncMock:
    """Create a mock httpx AsyncClient for T3K OAuth API."""
    return AsyncMock(spec=AsyncClient)


@pytest.fixture
def oauth_manager(
    db_session: AsyncSession, encryption_key: str, mock_httpx_client: AsyncMock
) -> T3KOAuthManager:
    """Create a T3KOAuthManager with mocked dependencies."""
    manager = T3KOAuthManager(
        session=db_session,
        encryption_key=encryption_key,
        client_id="test-client-id",
        client_secret="test-client-secret",
        oauth_base_url="https://oauth.tone3000.com",
    )
    manager._client = mock_httpx_client
    return manager


class TestTokenEncryption:
    """Test Fernet encryption and decryption of OAuth tokens."""

    async def test_encrypts_access_token_at_rest(
        self, oauth_manager: T3KOAuthManager, db_session: AsyncSession, encryption_key: str
    ) -> None:
        """Access tokens are encrypted using Fernet before persisting to DB."""
        plaintext_token = "test-access-token-12345"
        encrypted = oauth_manager._encrypt(plaintext_token)

        # Encrypted value should be different from plaintext
        assert encrypted != plaintext_token

        # Decryption should recover original value
        fernet = Fernet(encryption_key.encode())
        decrypted = fernet.decrypt(encrypted.encode()).decode()
        assert decrypted == plaintext_token

    async def test_encrypts_refresh_token_at_rest(
        self, oauth_manager: T3KOAuthManager, encryption_key: str
    ) -> None:
        """Refresh tokens are encrypted using Fernet before persisting to DB."""
        plaintext_token = "test-refresh-token-67890"
        encrypted = oauth_manager._encrypt(plaintext_token)

        # Encrypted value should be different from plaintext
        assert encrypted != plaintext_token

        # Decryption should recover original value
        fernet = Fernet(encryption_key.encode())
        decrypted = fernet.decrypt(encrypted.encode()).decode()
        assert decrypted == plaintext_token

    async def test_decrypts_access_token_from_database(
        self, oauth_manager: T3KOAuthManager, db_session: AsyncSession
    ) -> None:
        """OAuthManager decrypts tokens when reading from database."""
        plaintext_token = "test-access-token-abcde"
        encrypted_token = oauth_manager._encrypt(plaintext_token)

        # Store encrypted token in DB
        token_record = OAuthToken(
            id=1,
            access_token_encrypted=encrypted_token,
            refresh_token_encrypted=oauth_manager._encrypt("refresh-token"),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            created_at=datetime.now(UTC),
        )
        db_session.add(token_record)
        await db_session.commit()

        # Decrypt should recover plaintext
        decrypted = oauth_manager._decrypt(token_record.access_token_encrypted)
        assert decrypted == plaintext_token


class TestTokenExpiry:
    """Test token expiry checks and automatic refresh logic."""

    async def test_token_is_expired_when_past_expires_at(
        self, oauth_manager: T3KOAuthManager, db_session: AsyncSession
    ) -> None:
        """Token is considered expired when current time > expires_at."""
        token = OAuthToken(
            id=1,
            access_token_encrypted=oauth_manager._encrypt("token"),
            refresh_token_encrypted=oauth_manager._encrypt("refresh"),
            expires_at=datetime.now(UTC) - timedelta(minutes=5),  # 5 minutes ago
            created_at=datetime.now(UTC) - timedelta(hours=1),
        )
        db_session.add(token)
        await db_session.commit()

        assert oauth_manager._is_expired(token) is True

    async def test_token_is_not_expired_when_before_expires_at(
        self, oauth_manager: T3KOAuthManager, db_session: AsyncSession
    ) -> None:
        """Token is not expired when current time < expires_at."""
        token = OAuthToken(
            id=1,
            access_token_encrypted=oauth_manager._encrypt("token"),
            refresh_token_encrypted=oauth_manager._encrypt("refresh"),
            expires_at=datetime.now(UTC) + timedelta(hours=1),  # 1 hour from now
            created_at=datetime.now(UTC),
        )
        db_session.add(token)
        await db_session.commit()

        assert oauth_manager._is_expired(token) is False

    async def test_token_near_expiry_triggers_refresh(
        self, oauth_manager: T3KOAuthManager, db_session: AsyncSession, mock_httpx_client: AsyncMock
    ) -> None:
        """Token is refreshed preemptively when within 5 minutes of expiry."""
        # Create a token expiring in 3 minutes
        token = OAuthToken(
            id=1,
            access_token_encrypted=oauth_manager._encrypt("old-token"),
            refresh_token_encrypted=oauth_manager._encrypt("refresh-token"),
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            created_at=datetime.now(UTC) - timedelta(hours=1),
        )
        db_session.add(token)
        await db_session.commit()

        # Mock OAuth refresh endpoint
        mock_httpx_client.post.return_value = Response(
            status_code=200,
            json={
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            },
            request=Request("POST", "https://oauth.tone3000.com/token"),
        )

        # get_valid_token should refresh automatically
        valid_token = await oauth_manager.get_valid_token()
        assert valid_token == "new-access-token"

        # Verify refresh was called
        mock_httpx_client.post.assert_called_once()


class TestTokenRefresh:
    """Test OAuth token refresh flow."""

    async def test_refresh_token_calls_oauth_endpoint(
        self, oauth_manager: T3KOAuthManager, db_session: AsyncSession, mock_httpx_client: AsyncMock
    ) -> None:
        """refresh_token() calls T3K OAuth endpoint with refresh_token grant."""
        # Store existing token
        old_token = OAuthToken(
            id=1,
            access_token_encrypted=oauth_manager._encrypt("old-access"),
            refresh_token_encrypted=oauth_manager._encrypt("old-refresh"),
            expires_at=datetime.now(UTC) - timedelta(minutes=10),
            created_at=datetime.now(UTC) - timedelta(hours=2),
        )
        db_session.add(old_token)
        await db_session.commit()

        # Mock OAuth refresh response
        mock_httpx_client.post.return_value = Response(
            status_code=200,
            json={
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            },
            request=Request("POST", "https://oauth.tone3000.com/token"),
        )

        await oauth_manager.refresh_token()

        # Verify OAuth endpoint was called
        call_args = mock_httpx_client.post.call_args
        assert "/token" in str(call_args[0][0])
        assert call_args[1]["data"]["grant_type"] == "refresh_token"
        assert call_args[1]["data"]["refresh_token"] == "old-refresh"

    async def test_refresh_token_persists_new_tokens(
        self, oauth_manager: T3KOAuthManager, db_session: AsyncSession, mock_httpx_client: AsyncMock
    ) -> None:
        """refresh_token() persists new tokens (encrypted) to database."""
        # Store existing token
        old_token = OAuthToken(
            id=1,
            access_token_encrypted=oauth_manager._encrypt("old-access"),
            refresh_token_encrypted=oauth_manager._encrypt("old-refresh"),
            expires_at=datetime.now(UTC) - timedelta(minutes=10),
            created_at=datetime.now(UTC) - timedelta(hours=2),
        )
        db_session.add(old_token)
        await db_session.commit()

        # Mock OAuth refresh response
        mock_httpx_client.post.return_value = Response(
            status_code=200,
            json={
                "access_token": "refreshed-access-token",
                "refresh_token": "refreshed-refresh-token",
                "expires_in": 3600,
            },
            request=Request("POST", "https://oauth.tone3000.com/token"),
        )

        await oauth_manager.refresh_token()

        # Verify new tokens are persisted (encrypted)
        result = await db_session.execute(select(OAuthToken).where(OAuthToken.id == 1))
        updated_token = result.scalar_one()

        # Decrypt and verify
        decrypted_access = oauth_manager._decrypt(updated_token.access_token_encrypted)
        decrypted_refresh = oauth_manager._decrypt(updated_token.refresh_token_encrypted)

        assert decrypted_access == "refreshed-access-token"
        assert decrypted_refresh == "refreshed-refresh-token"

    async def test_refresh_token_updates_expires_at(
        self, oauth_manager: T3KOAuthManager, db_session: AsyncSession, mock_httpx_client: AsyncMock
    ) -> None:
        """refresh_token() updates expires_at based on expires_in from OAuth response."""
        old_token = OAuthToken(
            id=1,
            access_token_encrypted=oauth_manager._encrypt("old-access"),
            refresh_token_encrypted=oauth_manager._encrypt("old-refresh"),
            expires_at=datetime.now(UTC) - timedelta(hours=1),
            created_at=datetime.now(UTC) - timedelta(hours=2),
        )
        db_session.add(old_token)
        await db_session.commit()

        before_refresh = datetime.now(UTC)

        # Mock OAuth response with 7200 seconds (2 hours) expiry
        mock_httpx_client.post.return_value = Response(
            status_code=200,
            json={
                "access_token": "new-token",
                "refresh_token": "new-refresh",
                "expires_in": 7200,
            },
            request=Request("POST", "https://oauth.tone3000.com/token"),
        )

        await oauth_manager.refresh_token()

        # Verify expires_at is updated
        result = await db_session.execute(select(OAuthToken).where(OAuthToken.id == 1))
        updated_token = result.scalar_one()

        # Should be approximately 2 hours from now (within 10 seconds tolerance)
        expected_expiry = before_refresh + timedelta(seconds=7200)
        assert abs((updated_token.expires_at - expected_expiry).total_seconds()) < 10


class TestGetValidToken:
    """Test get_valid_token() method (main public API)."""

    async def test_get_valid_token_returns_decrypted_token_when_not_expired(
        self, oauth_manager: T3KOAuthManager, db_session: AsyncSession
    ) -> None:
        """get_valid_token() returns decrypted access token when not expired."""
        token = OAuthToken(
            id=1,
            access_token_encrypted=oauth_manager._encrypt("valid-access-token"),
            refresh_token_encrypted=oauth_manager._encrypt("refresh-token"),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            created_at=datetime.now(UTC),
        )
        db_session.add(token)
        await db_session.commit()

        valid_token = await oauth_manager.get_valid_token()
        assert valid_token == "valid-access-token"

    async def test_get_valid_token_refreshes_when_expired(
        self, oauth_manager: T3KOAuthManager, db_session: AsyncSession, mock_httpx_client: AsyncMock
    ) -> None:
        """get_valid_token() automatically refreshes token when expired."""
        expired_token = OAuthToken(
            id=1,
            access_token_encrypted=oauth_manager._encrypt("expired-token"),
            refresh_token_encrypted=oauth_manager._encrypt("refresh-token"),
            expires_at=datetime.now(UTC) - timedelta(minutes=30),
            created_at=datetime.now(UTC) - timedelta(hours=2),
        )
        db_session.add(expired_token)
        await db_session.commit()

        # Mock OAuth refresh
        mock_httpx_client.post.return_value = Response(
            status_code=200,
            json={
                "access_token": "refreshed-token",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            },
            request=Request("POST", "https://oauth.tone3000.com/token"),
        )

        valid_token = await oauth_manager.get_valid_token()
        assert valid_token == "refreshed-token"

    async def test_get_valid_token_raises_when_no_token_in_database(
        self, oauth_manager: T3KOAuthManager, db_session: AsyncSession
    ) -> None:
        """get_valid_token() raises exception when no token exists in database."""
        with pytest.raises(RuntimeError, match="No OAuth token found"):
            await oauth_manager.get_valid_token()


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
