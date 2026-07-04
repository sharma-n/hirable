from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import profile_history_agent_debounce_minutes, profile_history_max_versions
from app.db.models import Profile, ProfileVersion


def _snapshot(db: Session, profile: Profile, source: str) -> None:
    """Insert a pre-change snapshot of ``profile``'s current data, then prune."""
    db.add(
        ProfileVersion(
            user_id=profile.user_id,
            version=profile.version,
            data=profile.data,
            source=source,
        )
    )
    db.flush()
    _prune(db, profile.user_id)


def _prune(db: Session, user_id: str) -> None:
    max_versions = profile_history_max_versions()
    ids = [
        row.id
        for row in db.query(ProfileVersion.id)
        .filter_by(user_id=user_id)
        .order_by(ProfileVersion.created_at.desc())
        .all()
    ]
    stale_ids = ids[max_versions:]
    if stale_ids:
        db.query(ProfileVersion).filter(ProfileVersion.id.in_(stale_ids)).delete(
            synchronize_session=False
        )


def snapshot_profile(db: Session, profile: Profile, source: str) -> None:
    """Snapshot the profile's pre-change state. Called on every explicit user
    save (``PUT /api/profile``, resume re-upload) and on restore — always
    unconditionally, no debounce (a user's own deliberate save is always its
    own undo step)."""
    _snapshot(db, profile, source)


def snapshot_for_agent_write(db: Session, profile: Profile) -> None:
    """Snapshot before an agent-initiated write, debounced.

    A whole conversation's burst of tool-call edits should coalesce into ONE
    undo step ("before the agent's edits"), not one snapshot per tool call.
    Skip the snapshot if the newest existing version is already agent-sourced
    and still within the debounce window — the pending write just joins that
    same "agent editing session" version instead of starting a new one.
    """
    newest: ProfileVersion | None = (
        db.query(ProfileVersion)
        .filter_by(user_id=profile.user_id)
        .order_by(ProfileVersion.created_at.desc())
        .first()
    )
    if newest is not None and newest.source == "agent":
        window = timedelta(minutes=profile_history_agent_debounce_minutes())
        # SQLite drops tzinfo on readback even for DateTime(timezone=True) columns
        # (see app/auth/sessions.py's identical .replace(tzinfo=...) pattern).
        created_at = newest.created_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created_at < window:
            return
    _snapshot(db, profile, "agent")
