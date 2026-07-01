from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session as DBSession

from app.db.models import Session, User

COOKIE_NAME = "hirable_session"
_TTL_DAYS = 14


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: DBSession, user_id: str) -> str:
    """Create a new session. Returns the raw token (stored only in the cookie)."""
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=_TTL_DAYS)
    session = Session(token_hash=token_hash, user_id=user_id, expires_at=expires_at)
    db.add(session)
    db.commit()
    return token


def resolve_session(db: DBSession, token: str) -> User | None:
    """Return the User for a valid, unexpired token, or None."""
    token_hash = _hash_token(token)
    session = db.get(Session, token_hash)
    if session is None:
        return None
    if session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        return None
    user = session.user
    if not user.is_active:
        return None
    return user


def delete_session(db: DBSession, token: str) -> None:
    token_hash = _hash_token(token)
    session = db.get(Session, token_hash)
    if session:
        db.delete(session)
        db.commit()


def delete_user_sessions(db: DBSession, user_id: str) -> None:
    """Invalidate all sessions for a user (logout all devices)."""
    db.query(Session).filter(Session.user_id == user_id).delete()
    db.commit()


def set_session_cookie(response: object, token: str, *, secure: bool = False) -> None:
    """Set the httpOnly session cookie on a FastAPI Response."""
    response.set_cookie(  # type: ignore[attr-defined]
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
        max_age=_TTL_DAYS * 86400,
    )


def clear_session_cookie(response: object, *, secure: bool = False) -> None:
    response.delete_cookie(  # type: ignore[attr-defined]
        key=COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )
