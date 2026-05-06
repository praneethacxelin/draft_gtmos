"""Symmetric encryption for API keys stored in the DB."""
import os
from cryptography.fernet import Fernet


def _key() -> bytes:
    raw = os.environ.get("ENCRYPTION_KEY")
    if not raw:
        raise RuntimeError("ENCRYPTION_KEY env var is required")
    return raw.encode()


def encrypt(value: str) -> str:
    return Fernet(_key()).encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    return Fernet(_key()).decrypt(token.encode()).decode()
