"""
AES-256-GCM encryption utilities for encrypting and decrypting data.

This module provides reusable encryption/decryption methods for:
- Text data (transcripts, summaries, etc.)
- Binary data (audio files, documents, etc.)

All encryption uses AES-256-GCM with format: [IV (16 bytes)] + [Ciphertext] + [Tag (16 bytes)]
"""

import uuid
import base64
from Crypto.Cipher import AES
from loguru import logger


class AESEncryption:
    """Utility class for AES-256-GCM encryption/decryption."""

    @staticmethod
    def encrypt_text(plaintext: str, encryption_key_b64: str) -> str:
        """
        Encrypt plaintext string using AES-256-GCM.

        Args:
            plaintext: Text to encrypt
            encryption_key_b64: Base64-encoded 256-bit encryption key

        Returns:
            Base64-encoded encrypted data (IV + ciphertext + tag)

        Raises:
            Exception: If encryption fails
        """
        try:
            # Decode encryption key from base64
            key = base64.b64decode(encryption_key_b64)

            # Generate random 16-byte IV
            iv = uuid.uuid4().bytes[:16]

            # Convert plaintext to bytes
            plaintext_bytes = plaintext.encode('utf-8')

            # Encrypt using AES-256-GCM
            cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
            ciphertext, tag = cipher.encrypt_and_digest(plaintext_bytes)

            # Combine IV + ciphertext + tag and encode as base64
            encrypted_data = iv + ciphertext + tag
            encrypted_b64 = base64.b64encode(encrypted_data).decode('utf-8')

            logger.info(f"[ENCRYPT] Text encrypted: {len(plaintext_bytes)} bytes → {len(encrypted_b64)} bytes (base64)")
            return encrypted_b64

        except Exception as e:
            logger.error(f"[ERROR] Failed to encrypt text: {e}", exc_info=True)
            raise

    @staticmethod
    def decrypt_text(encrypted_b64: str, encryption_key_b64: str) -> str:
        """
        Decrypt base64-encoded ciphertext to plaintext using AES-256-GCM.

        Args:
            encrypted_b64: Base64-encoded encrypted data (IV + ciphertext + tag)
            encryption_key_b64: Base64-encoded 256-bit encryption key

        Returns:
            Decrypted plaintext string

        Raises:
            Exception: If decryption fails or authentication fails
        """
        try:
            # Decode encryption key from base64
            key = base64.b64decode(encryption_key_b64)

            # Decode encrypted data from base64
            encrypted_data = base64.b64decode(encrypted_b64)

            # Extract IV, ciphertext, and tag
            iv = encrypted_data[:16]
            ciphertext = encrypted_data[16:-16]
            tag = encrypted_data[-16:]

            # Decrypt using AES-256-GCM
            cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
            plaintext_bytes = cipher.decrypt_and_verify(ciphertext, tag)

            # Convert bytes back to string
            plaintext = plaintext_bytes.decode('utf-8')

            logger.info(f"[DECRYPT] Text decrypted: {len(plaintext_bytes)} bytes")
            return plaintext

        except Exception as e:
            logger.error(f"[ERROR] Failed to decrypt text: {e}", exc_info=True)
            raise

    @staticmethod
    def encrypt_bytes(data: bytes, encryption_key_b64: str) -> bytes:
        """
        Encrypt binary data using AES-256-GCM.

        Args:
            data: Binary data to encrypt
            encryption_key_b64: Base64-encoded 256-bit encryption key

        Returns:
            Encrypted data (IV + ciphertext + tag) as raw bytes

        Raises:
            Exception: If encryption fails
        """
        try:
            # Decode encryption key from base64
            key = base64.b64decode(encryption_key_b64)

            # Generate random 16-byte IV
            iv = uuid.uuid4().bytes[:16]

            # Encrypt using AES-256-GCM
            cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
            ciphertext, tag = cipher.encrypt_and_digest(data)

            # Combine IV + ciphertext + tag
            encrypted_data = iv + ciphertext + tag

            logger.info(f"[ENCRYPT] Bytes encrypted: {len(data)} bytes → {len(encrypted_data)} bytes")
            return encrypted_data

        except Exception as e:
            logger.error(f"[ERROR] Failed to encrypt bytes: {e}", exc_info=True)
            raise

    @staticmethod
    def decrypt_bytes(encrypted_data: bytes, encryption_key_b64: str) -> bytes:
        """
        Decrypt binary data using AES-256-GCM.

        Args:
            encrypted_data: Encrypted data (IV + ciphertext + tag) as raw bytes
            encryption_key_b64: Base64-encoded 256-bit encryption key

        Returns:
            Decrypted binary data

        Raises:
            Exception: If decryption fails or authentication fails
        """
        try:
            # Decode encryption key from base64
            key = base64.b64decode(encryption_key_b64)

            # Extract IV, ciphertext, and tag
            iv = encrypted_data[:16]
            ciphertext = encrypted_data[16:-16]
            tag = encrypted_data[-16:]

            # Decrypt using AES-256-GCM
            cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)

            logger.info(f"[DECRYPT] Bytes decrypted: {len(plaintext)} bytes")
            return plaintext

        except Exception as e:
            logger.error(f"[ERROR] Failed to decrypt bytes: {e}", exc_info=True)
            raise


# Singleton instance for convenience
aes_encryption = AESEncryption()
