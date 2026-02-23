"""Simple symmetric encryption for storing OAuth tokens and bank references at rest.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the cryptography library.
Falls back to base64 identity encoding when TOKEN_ENCRYPTION_KEY is unset
(dev/test only — not secure for production).
"""

import base64

from app.core.settings import settings

_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is not None:
        return _fernet
    key = settings.token_encryption_key
    if not key:
        return None
    from cryptography.fernet import Fernet

    _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_token(plaintext: str) -> str:
    """Encrypt a plaintext token. Returns base64-encoded ciphertext."""
    f = _get_fernet()
    if f is None:
        # Dev fallback: base64 encode only (NOT secure)
        return base64.b64encode(plaintext.encode()).decode()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a ciphertext token. Returns plaintext."""
    f = _get_fernet()
    if f is None:
        return base64.b64decode(ciphertext.encode()).decode()
    return f.decrypt(ciphertext.encode()).decode()
