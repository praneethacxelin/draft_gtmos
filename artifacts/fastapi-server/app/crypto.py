"""Symmetric encryption for API keys stored in the DB."""
import base64
import hashlib
import hmac
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


# ---------- Password hashing (PBKDF2-HMAC-SHA256, stdlib only) ----------

_PBKDF2_ROUNDS = 240_000


def hash_password(password: str) -> str:
    """Return a salted PBKDF2 hash encoded as ``pbkdf2_sha256$rounds$salt$hash``."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return "pbkdf2_sha256${}${}${}".format(
        _PBKDF2_ROUNDS,
        base64.b64encode(salt).decode(),
        base64.b64encode(dk).decode(),
    )


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time check of ``password`` against a stored PBKDF2 hash."""
    if not stored:
        return False
    try:
        algo, rounds_s, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        rounds = int(rounds_s)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds)
    return hmac.compare_digest(dk, expected)
