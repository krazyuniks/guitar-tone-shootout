"""Token encryption using Fernet for at-rest security.

Provides symmetric encryption for OAuth tokens stored in .gts-auth.json.
Uses Fernet (symmetric encryption with HMAC) from the cryptography library.
"""

import os

from cryptography.fernet import Fernet


class TokenEncryptor:
    """Encrypts and decrypts tokens using Fernet symmetric encryption.

    Uses a Fernet key which can be:
    - Provided explicitly via constructor
    - Read from GTS_ENCRYPTION_KEY environment variable
    - Generated automatically (not recommended for production)
    """

    def __init__(self, key: str | bytes | None = None) -> None:
        """Initialize token encryptor.

        Args:
            key: Fernet encryption key (base64-encoded 32-byte key).
                 If None, reads from GTS_ENCRYPTION_KEY environment variable.
                 If env var not set, generates a new key (unsafe for production).
        """
        if key is None:
            # Try environment variable first
            key = os.environ.get("GTS_ENCRYPTION_KEY")
            if key is None:
                # Generate new key (unsafe - only for testing)
                key = self.generate_key()

        # Convert string to bytes if needed
        if isinstance(key, str):
            key = key.encode("utf-8")

        self._fernet = Fernet(key)

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet encryption key.

        Returns:
            Base64-encoded 32-byte key suitable for Fernet encryption.
            Key is 44 characters when base64-encoded.
        """
        key_bytes = Fernet.generate_key()
        return key_bytes.decode("utf-8")

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext token.

        Args:
            plaintext: Token to encrypt

        Returns:
            Encrypted token (base64-encoded)
        """
        # Convert string to bytes
        plaintext_bytes = plaintext.encode("utf-8")

        # Encrypt
        encrypted_bytes = self._fernet.encrypt(plaintext_bytes)

        # Return as string
        return encrypted_bytes.decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt an encrypted token.

        Args:
            ciphertext: Encrypted token (base64-encoded)

        Returns:
            Decrypted plaintext token

        Raises:
            cryptography.fernet.InvalidToken: If decryption fails
        """
        # Convert string to bytes
        ciphertext_bytes = ciphertext.encode("utf-8")

        # Decrypt
        decrypted_bytes = self._fernet.decrypt(ciphertext_bytes)

        # Return as string
        return decrypted_bytes.decode("utf-8")
