"""Password hashing using stdlib PBKDF2-HMAC-SHA256."""

from __future__ import annotations

import hashlib
import os


def hash_password(password: str) -> str:
    """Return a salted PBKDF2 hash of password."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return salt.hex() + ":" + key.hex()


def verify_password(password: str, stored: str) -> bool:
    """Return True if password matches the stored hash."""
    try:
        salt_hex, key_hex = stored.split(":", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return key.hex() == key_hex
