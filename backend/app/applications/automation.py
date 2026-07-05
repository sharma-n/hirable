"""Background staleness/auto-reject automation (M7, SPEC §9). Kept as a pure
function of (db, now) — rather than reading datetime.now() internally — so
tests can inject a fixed ``now`` against seeded, backdated rows instead of
waiting on real wall-clock time.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.applications.service import transition_stage
from app.applications.stages import ACTIVE_STAGES, STALE_OR_ACTIVE
from app.config import tracking_auto_reject_after_days, tracking_stale_after_days
from app.db.models import Application


def apply_automation(db: Session, now: datetime) -> None:
    """Mark idle applications Stale, then Rejected, per app.tracking's
    configured thresholds.

    Checks the (longer) auto-reject threshold before the (shorter) stale
    threshold so an application that's been idle long enough to skip straight
    past "Stale" jumps directly to "Rejected" in one pass, instead of getting
    stuck at "Stale" until the next scheduler run.
    """
    stale_after = timedelta(days=tracking_stale_after_days())
    reject_after = timedelta(days=tracking_auto_reject_after_days())

    applications = db.query(Application).filter(Application.stage.in_(STALE_OR_ACTIVE)).all()
    for application in applications:
        # SQLite drops tzinfo on readback even for DateTime(timezone=True)
        # columns (see app/auth/sessions.py's identical .replace(tzinfo=...)
        # pattern, and app/db/profile_history.py's).
        last_activity = application.last_activity_at.replace(tzinfo=timezone.utc)
        idle = now - last_activity

        if idle >= reject_after:
            transition_stage(
                db,
                application,
                "Rejected",
                actor="automation",
                note=f"Auto-rejected after {reject_after.days} days of inactivity",
            )
        elif idle >= stale_after and application.stage in ACTIVE_STAGES:
            transition_stage(
                db,
                application,
                "Stale",
                actor="automation",
                note=f"Auto-marked stale after {stale_after.days} days of inactivity",
            )
