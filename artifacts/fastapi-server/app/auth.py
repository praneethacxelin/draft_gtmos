"""Authentication.

Basic JWT bearer-token auth layered on top of the original no-auth shim.

- A signed token is issued at login/register and sent as
  ``Authorization: Bearer <token>``.
- ``current_user`` decodes the token and loads that user. When no valid token
  is present it falls back to the shared ``user_public`` row so existing
  unauthenticated/demo flows keep working — unless ``AUTH_REQUIRED=1`` is set,
  in which case anonymous requests are rejected with 401.
"""
from __future__ import annotations

import os
import time

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import User, get_session

PUBLIC_USER_ID = "user_public"
PUBLIC_USER_EMAIL = "public@gtmos.local"

_ALGO = "HS256"
_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


def _secret() -> str:
    return (
        os.environ.get("AUTH_SECRET")
        or os.environ.get("ENCRYPTION_KEY")
        or "dev-insecure-auth-secret"
    )


def _auth_required() -> bool:
    return os.environ.get("AUTH_REQUIRED", "").lower() in ("1", "true", "yes")


def issue_token(user: User) -> str:
    now = int(time.time())
    payload = {
        "sub": user.id,
        "email": user.email,
        "iat": now,
        "exp": now + _TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGO)


def _decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, _secret(), algorithms=[_ALGO])
    except jwt.PyJWTError:
        return None


def _get_or_create_public(db: Session) -> User:
    user = db.query(User).filter(User.id == PUBLIC_USER_ID).first()
    if user is None:
        user = User(id=PUBLIC_USER_ID, email=PUBLIC_USER_EMAIL)
        db.add(user)
        try:
            db.commit()
        except Exception:
            db.rollback()
            user = db.query(User).filter(User.id == PUBLIC_USER_ID).first()
        else:
            db.refresh(user)
    return user


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not header:
        return None
    parts = header.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
        return parts[1].strip()
    return None


def current_user(
    request: Request,
    db: Session = Depends(get_session),
) -> User:
    token = _bearer_token(request)
    if token:
        payload = _decode_token(token)
        if payload and payload.get("sub"):
            user = db.query(User).filter(User.id == payload["sub"]).first()
            if user is not None:
                return user
        # A token was supplied but is invalid/expired/unknown.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if _auth_required():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _get_or_create_public(db)

