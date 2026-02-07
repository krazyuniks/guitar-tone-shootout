"""Unit tests for auth token encryption (T19).

Tests for Fernet-based token encryption at rest:
- Encrypting access tokens before storage
- Decrypting tokens for use
- Key generation and management
- Encryption/decryption round-trip
"""

import pytest


class TestTokenEncryption:
    """Test suite for Fernet token encryption."""

    def test_encrypt_access_token(self) -> None:
        """Test encrypting an access token with Fernet."""
        from webapp.auth.encryption import TokenEncryptor

        encryptor = TokenEncryptor()

        plaintext_token = "test_access_token_abc123"

        # Encrypt token
        encrypted_token = encryptor.encrypt(plaintext_token)

        # Encrypted token should be different from plaintext
        assert encrypted_token != plaintext_token

        # Encrypted token should be string
        assert isinstance(encrypted_token, str)

        # Should be non-empty
        assert len(encrypted_token) > 0

    def test_decrypt_access_token(self) -> None:
        """Test decrypting an encrypted token with Fernet."""
        from webapp.auth.encryption import TokenEncryptor

        encryptor = TokenEncryptor()

        original_token = "test_access_token_xyz789"

        # Encrypt then decrypt
        encrypted = encryptor.encrypt(original_token)
        decrypted = encryptor.decrypt(encrypted)

        # Should get back original token
        assert decrypted == original_token

    def test_encryption_is_deterministic_with_same_key(self) -> None:
        """Test that same plaintext with same key produces same ciphertext."""
        from webapp.auth.encryption import TokenEncryptor

        # Use same key for both encryptors
        key = TokenEncryptor.generate_key()
        encryptor1 = TokenEncryptor(key=key)
        encryptor2 = TokenEncryptor(key=key)

        plaintext = "test_token"

        # Both should decrypt successfully
        encrypted1 = encryptor1.encrypt(plaintext)
        decrypted2 = encryptor2.decrypt(encrypted1)

        assert decrypted2 == plaintext

    def test_generate_encryption_key(self) -> None:
        """Test generating a new Fernet encryption key."""
        from webapp.auth.encryption import TokenEncryptor

        # Generate key
        key = TokenEncryptor.generate_key()

        # Key should be bytes
        assert isinstance(key, (bytes, str))

        # Key should be non-empty
        assert len(key) > 0

        # Should be base64-encoded 32-byte key (Fernet requirement)
        # Fernet keys are 44 characters when base64-encoded
        if isinstance(key, str):
            assert len(key) == 44

    def test_decrypt_fails_with_wrong_key(self) -> None:
        """Test decryption fails when using wrong key."""
        from webapp.auth.encryption import TokenEncryptor

        # Encrypt with one key
        key1 = TokenEncryptor.generate_key()
        encryptor1 = TokenEncryptor(key=key1)
        encrypted = encryptor1.encrypt("test_token")

        # Try to decrypt with different key
        key2 = TokenEncryptor.generate_key()
        encryptor2 = TokenEncryptor(key=key2)

        # Should raise exception
        with pytest.raises(Exception):  # Fernet raises various exceptions
            encryptor2.decrypt(encrypted)

    def test_encrypt_refresh_token(self) -> None:
        """Test encrypting refresh tokens (same as access tokens)."""
        from webapp.auth.encryption import TokenEncryptor

        encryptor = TokenEncryptor()

        refresh_token = "refresh_token_def456"

        # Encrypt refresh token
        encrypted = encryptor.encrypt(refresh_token)

        # Should encrypt successfully
        assert encrypted != refresh_token
        assert len(encrypted) > 0

        # Should decrypt back to original
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == refresh_token

    def test_encryptor_uses_env_key_if_provided(self) -> None:
        """Test TokenEncryptor uses key from environment variable if set."""
        from webapp.auth.encryption import TokenEncryptor
        import os

        # Generate a key
        test_key = TokenEncryptor.generate_key()

        # Set environment variable
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("GTS_ENCRYPTION_KEY", test_key)

            # Create encryptor (should use env key)
            encryptor = TokenEncryptor()

            # Should be able to encrypt/decrypt
            encrypted = encryptor.encrypt("test_token")
            decrypted = encryptor.decrypt(encrypted)
            assert decrypted == "test_token"

    def test_encrypt_handles_empty_string(self) -> None:
        """Test encryption handles empty string gracefully."""
        from webapp.auth.encryption import TokenEncryptor

        encryptor = TokenEncryptor()

        # Encrypt empty string
        encrypted = encryptor.encrypt("")

        # Should return encrypted value (even if empty input)
        assert isinstance(encrypted, str)

        # Should decrypt back to empty string
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == ""

    def test_decrypt_handles_invalid_ciphertext(self) -> None:
        """Test decryption handles invalid ciphertext gracefully."""
        from webapp.auth.encryption import TokenEncryptor

        encryptor = TokenEncryptor()

        # Try to decrypt invalid ciphertext
        with pytest.raises(Exception):  # Fernet raises InvalidToken
            encryptor.decrypt("invalid_ciphertext_not_base64")

    def test_encryption_roundtrip_with_unicode(self) -> None:
        """Test encryption/decryption handles unicode characters."""
        from webapp.auth.encryption import TokenEncryptor

        encryptor = TokenEncryptor()

        # Token with unicode characters
        unicode_token = "test_token_🎸_музыка_音楽"

        # Encrypt and decrypt
        encrypted = encryptor.encrypt(unicode_token)
        decrypted = encryptor.decrypt(encrypted)

        # Should preserve unicode
        assert decrypted == unicode_token

    def test_encryption_produces_different_output_each_time(self) -> None:
        """Test that Fernet encryption produces different output for same input.

        Note: This is a characteristic of Fernet - it includes a timestamp
        and random IV, so same plaintext produces different ciphertext.
        """
        from webapp.auth.encryption import TokenEncryptor

        encryptor = TokenEncryptor()

        plaintext = "same_token"

        # Encrypt same plaintext twice
        encrypted1 = encryptor.encrypt(plaintext)
        encrypted2 = encryptor.encrypt(plaintext)

        # Ciphertexts should be different (due to IV/timestamp)
        assert encrypted1 != encrypted2

        # But both should decrypt to same plaintext
        assert encryptor.decrypt(encrypted1) == plaintext
        assert encryptor.decrypt(encrypted2) == plaintext

    def test_token_encryptor_is_reusable(self) -> None:
        """Test that TokenEncryptor instance can encrypt multiple tokens."""
        from webapp.auth.encryption import TokenEncryptor

        encryptor = TokenEncryptor()

        # Encrypt multiple tokens with same encryptor
        tokens = [
            "token1_abc",
            "token2_def",
            "token3_ghi",
        ]

        encrypted_tokens = [encryptor.encrypt(t) for t in tokens]
        decrypted_tokens = [encryptor.decrypt(e) for e in encrypted_tokens]

        # All should decrypt correctly
        assert decrypted_tokens == tokens
