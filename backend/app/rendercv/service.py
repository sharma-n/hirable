"""Shared draft_cv/draft_cover_letter logic — used by both the internal
agent-tool routes (app/internal/documents.py) and the public API
(app/api/documents.py), so generating a document works identically whether
triggered by the agent or a UI button.
"""
from __future__ import annotations

from llm_kit import LLMClient
from sqlalchemy.orm import Session

from app.config import rendercv_theme
from app.db.models import Document, Job, Profile
from app.rendercv.build import build_rendercv_yaml
from app.rendercv.letter import build_cover_letter_yaml, tailor_cover_letter
from app.rendercv.tailor import tailor_profile


def _next_version(db: Session, user_id: str, job_id: str, doc_type: str) -> int:
    latest: Document | None = (
        db.query(Document)
        .filter_by(user_id=user_id, job_id=job_id, type=doc_type)
        .order_by(Document.version.desc())
        .first()
    )
    return (latest.version + 1) if latest else 1


async def draft_cv_document(
    db: Session,
    llm: LLMClient,
    job: Job,
    profile: Profile,
    instructions: str | None = None,
) -> Document:
    """Tailor the profile to ``job``, assemble RenderCV YAML, and persist the
    next version row for this (user, job, "cv") family. Callers are
    responsible for user-scoped 404 checks on ``job``/``profile`` before
    calling this."""
    tailored = await tailor_profile(llm, profile.data, job.parsed, instructions)
    source_text = build_rendercv_yaml(profile.data, tailored, job.parsed, rendercv_theme())

    document = Document(
        user_id=job.user_id,
        job_id=job.id,
        type="cv",
        source_text=source_text,
        version=_next_version(db, job.user_id, job.id, "cv"),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


async def draft_cover_letter_document(
    db: Session,
    llm: LLMClient,
    job: Job,
    profile: Profile,
    instructions: str | None = None,
) -> Document:
    """Tailor a cover letter to ``job`` and persist the next version row for
    this (user, job, "cover_letter") family — mirrors ``draft_cv_document``.
    Callers are responsible for user-scoped 404 checks on ``job``/``profile``
    before calling this."""
    tailored = await tailor_cover_letter(llm, profile.data, job.parsed, instructions)
    source_text = build_cover_letter_yaml(profile.data, tailored, rendercv_theme())

    document = Document(
        user_id=job.user_id,
        job_id=job.id,
        type="cover_letter",
        source_text=source_text,
        version=_next_version(db, job.user_id, job.id, "cover_letter"),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document
