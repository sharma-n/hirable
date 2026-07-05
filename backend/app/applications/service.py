"""Shared application-tracking logic (M7) — used by both the public API
(app/api/applications.py) and the internal agent-tool routes
(app/internal/applications.py), plus the background automation
(app/applications/automation.py), so a stage transition behaves identically
whether triggered by the UI, the agent, or the scheduler.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.applications.stages import ACTIVE_STAGES
from app.config import tracking_stale_after_days
from app.db.models import Application, ApplicationDocument, ApplicationEvent, Document, Job


def get_or_create_application(db: Session, job: Job) -> Application:
    existing = db.query(Application).filter_by(job_id=job.id).first()
    if existing is not None:
        return existing
    application = Application(user_id=job.user_id, job_id=job.id)
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


def backfill_applications(db: Session) -> int:
    """Idempotent startup backfill: ensure every existing job (ingested before
    M7 shipped) has an Application row. Returns the number created."""
    jobs_without_app = (
        db.query(Job)
        .outerjoin(Application, Application.job_id == Job.id)
        .filter(Application.id.is_(None))
        .all()
    )
    for job in jobs_without_app:
        db.add(Application(user_id=job.user_id, job_id=job.id))
    if jobs_without_app:
        db.commit()
    return len(jobs_without_app)


def finalize_documents(db: Session, application: Application) -> list[str]:
    """Finalize the latest CV + cover-letter Document versions for this
    application's job: flip is_finalized and record an ApplicationDocument
    snapshot row (storing only the document id — Document rows are already
    immutable/append-only, so no content copy is needed). Idempotent — skips
    a doc_type already recorded. Returns the doc_types that couldn't be
    finalized because no draft exists yet, for a caller-facing warning."""
    missing: list[str] = []
    for doc_type in ("cv", "cover_letter"):
        latest: Document | None = (
            db.query(Document)
            .filter_by(user_id=application.user_id, job_id=application.job_id, type=doc_type)
            .order_by(Document.version.desc())
            .first()
        )
        if latest is None:
            missing.append(doc_type)
            continue
        already = (
            db.query(ApplicationDocument)
            .filter_by(application_id=application.id, document_id=latest.id)
            .first()
        )
        if already is not None:
            continue
        latest.is_finalized = True
        db.add(
            ApplicationDocument(
                application_id=application.id, document_id=latest.id, doc_type=doc_type
            )
        )
    return missing


def transition_stage(
    db: Session,
    application: Application,
    to_stage: str,
    *,
    actor: str = "user",
    note: str | None = None,
) -> tuple[Application, list[str]]:
    """Transition ``application`` to ``to_stage``, recording an
    ApplicationEvent when the stage actually changes.

    ``actor`` distinguishes real activity ("user"/"agent") from the
    background automation ("automation") — only real activity resets
    ``last_activity_at``/``auto_stale_at``, so the automation's own writes
    don't reset the staleness clock they exist to advance. ``actor`` is also
    persisted onto the ``ApplicationEvent`` row (M8) so analytics can tell a
    genuine response apart from an automation-caused Stale/Rejected
    (ghosting).

    Entering "Applied" for the first time (``submitted_at is None``) snapshots
    the latest CV + cover-letter Document versions via ``finalize_documents``.
    Returns the updated application and any doc_types that couldn't be
    finalized (only non-empty when transitioning into "Applied").
    """
    from_stage = application.stage
    now = datetime.now(timezone.utc)
    missing_docs: list[str] = []

    if from_stage != to_stage:
        db.add(
            ApplicationEvent(
                application_id=application.id,
                from_stage=from_stage,
                to_stage=to_stage,
                note=note,
                actor=actor,
            )
        )
        application.stage = to_stage

    if actor != "automation":
        application.last_activity_at = now
        application.auto_stale_at = (
            now + timedelta(days=tracking_stale_after_days()) if to_stage in ACTIVE_STAGES else None
        )

    if to_stage == "Applied" and application.submitted_at is None:
        application.submitted_at = now
        missing_docs = finalize_documents(db, application)

    application.updated_at = now
    db.commit()
    db.refresh(application)
    return application, missing_docs
