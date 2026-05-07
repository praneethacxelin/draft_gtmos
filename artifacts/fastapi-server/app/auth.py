"""Clerk-based authentication for FastAPI.

Verifies the bearer token sent by the React app (issued by Clerk) using
Clerk's JWKS endpoint. The Clerk user id (the JWT ``sub``) is upserted
into the local ``users`` table on first request so we have a stable
foreign key for per-user data scoping.
"""
from __future__ import annotations

import base64
import logging
import os
import time
from typing import Optional

import httpx
import jwt
from jwt import PyJWKClient
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import User, get_session

log = logging.getLogger("gtm.auth")


def _decode_pk_host(pk: str) -> str:
    """Clerk publishable keys encode the Frontend API host in their suffix."""
    parts = pk.split("_", 2)
    if len(parts) < 3:
        raise RuntimeError("Invalid CLERK_PUBLISHABLE_KEY")
    encoded = parts[2]
    pad = "=" * (-len(encoded) % 4)
    decoded = base64.b64decode(encoded + pad).decode("utf-8", errors="ignore")
    return decoded.rstrip("$").rstrip("/")


_jwks_client: Optional[PyJWKClient] = None
_frontend_api_host: Optional[str] = None


def _jwks() -> PyJWKClient:
    global _jwks_client, _frontend_api_host
    if _jwks_client is None:
        pk = os.environ.get("CLERK_PUBLISHABLE_KEY", "")
        if not pk:
            raise HTTPException(500, "Auth not configured: CLERK_PUBLISHABLE_KEY missing")
        _frontend_api_host = _decode_pk_host(pk)
        _jwks_client = PyJWKClient(f"https://{_frontend_api_host}/.well-known/jwks.json")
    return _jwks_client


def _verify(token: str) -> dict:
    try:
        signing_key = _jwks().get_signing_key_from_jwt(token).key
        # Issuer for Clerk session tokens is the Frontend API host
        # (e.g. https://clerk.example.com). Verifying it prevents tokens
        # signed by a different Clerk tenant from being accepted.
        expected_iss = f"https://{_frontend_api_host}"
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=expected_iss,
            options={"verify_aud": False, "verify_iss": True},
        )
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"Invalid auth token: {e}")
    if int(claims.get("exp", 0)) < int(time.time()):
        raise HTTPException(401, "Token expired")
    return claims


def _fetch_email(user_id: str) -> Optional[str]:
    secret = os.environ.get("CLERK_SECRET_KEY", "")
    if not secret:
        return None
    try:
        with httpx.Client(timeout=10.0) as c:
            r = c.get(
                f"https://api.clerk.com/v1/users/{user_id}",
                headers={"Authorization": f"Bearer {secret}"},
            )
            if r.status_code != 200:
                return None
            data = r.json()
            primary_id = data.get("primary_email_address_id")
            for e in data.get("email_addresses") or []:
                if e.get("id") == primary_id:
                    return e.get("email_address")
            emails = data.get("email_addresses") or []
            return emails[0].get("email_address") if emails else None
    except Exception as e:
        log.warning("Clerk email lookup failed: %s", e)
        return None


def current_user(
    authorization: str = Header(default=""),
    db: Session = Depends(get_session),
) -> User:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    claims = _verify(token)
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(401, "Token missing subject")

    user = db.query(User).filter(User.id == sub).first()
    if user is None:
        user = User(id=sub, email=_fetch_email(sub))
        db.add(user)
        try:
            db.commit()
        except Exception:
            db.rollback()
            user = db.query(User).filter(User.id == sub).first()
        else:
            db.refresh(user)
    elif not user.email:
        email = _fetch_email(sub)
        if email:
            user.email = email
            db.commit()
    return user
