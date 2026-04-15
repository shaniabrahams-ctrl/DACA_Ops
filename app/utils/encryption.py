"""
Field-level encryption for sensitive data (EIN, account numbers).

Uses Fernet symmetric encryption (AES-128 in CBC mode with HMAC-SHA256).
Key is stored in FIELD_ENCRYPTION_KEY env var (base64-encoded 32 bytes).

Usage:
  encrypted = encrypt("123-45-6789")
  original = decrypt(encrypted)
"""
import base64
import os
from cryptography.fernet import Fernet


def _get_fernet() -> Fernet:
    from app.config import settings
    key = settings.field_encryption_key
    if not key:
        # In development without a key, generate a temporary one (NOT for production)
        key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return the encrypted value as a string."""
    if not plaintext:
        return ""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt an encrypted string and return the original plaintext."""
    if not ciphertext:
        return ""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()
