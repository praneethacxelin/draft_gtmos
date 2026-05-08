"""No-auth shim.

Authentication has been removed — every request is treated as the same
shared "public" user. This keeps the per-user foreign keys in the
schema valid without requiring sign-in.
"""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import User, get_session

PUBLIC_USER_ID = "user_public"
PUBLIC_USER_EMAIL = "public@gtmos.local"


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


def current_user(db: Session = Depends(get_session)) -> User:
    return _get_or_create_public(db)
