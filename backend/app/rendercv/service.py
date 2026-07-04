"""Shared draft_cv logic — used by both the internal agent-tool route
(app/internal/documents.py) and the public API (app/api/documents.py), so
generating a CV works identically whether triggered by the agent or a UI
button.
"""
from __future__ import annotations

from llm_kit import LLMClient
from sqlalchemy.orm import Session

from app.config import rendercv_theme
from app.db.models import Document, Job, Profile
from app.rendercv.build import build_rendercv_yaml
from app.rendercv.tailor import tailor_profile


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

    latest: Document | None = (
        db.query(Document)
        .filter_by(user_id=job.user_id, job_id=job.id, type="cv")
        .order_by(Document.version.desc())
        .first()
    )
    next_version = (latest.version + 1) if latest else 1

    document = Document(
        user_id=job.user_id,
        job_id=job.id,
        type="cv",
        source_text=source_text,
        version=next_version,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document
