"""Password-based admin authentication, independent of Clerk.

The admin password is read from the ``ADMIN_PASSWORD`` env var. Clients
POST it to ``/admin/login`` and receive an opaque token that they then
send back as ``X-Admin-Token`` (or ``Authorization: Bearer <token>``)
on subsequent admin endpoints.

The "token" is just an HMAC-SHA256 of a fixed payload using the
password as the key, so it's a deterministic value derived from the
secret. This is intentionally simple — no DB, no expiry — sufficient
for an internal admin console gated behind a long random password.
"""
from __future__ import annotations

import hmac
import hashlib
import os
from fastapi import Header, HTTPException


_ADMIN_PAYLOAD = b"gtm-admin-token-v1"


def _admin_password() -> str:
    pw = os.environ.get("ADMIN_PASSWORD", "").strip()
    if not pw:
        raise HTTPException(503, "Admin login is not configured on the server")
    return pw


def expected_token() -> str:
    pw = _admin_password()
    return hmac.new(pw.encode(), _ADMIN_PAYLOAD, hashlib.sha256).hexdigest()


def verify_password(password: str) -> bool:
    pw = _admin_password()
    return hmac.compare_digest(pw, password or "")


def require_admin(
    x_admin_token: str = Header(default=""),
    authorization: str = Header(default=""),
) -> None:
    token = x_admin_token.strip()
    if not token and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(401, "Missing admin token")
    if not hmac.compare_digest(token, expected_token()):
        raise HTTPException(401, "Invalid admin token")
