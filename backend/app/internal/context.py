from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_db
from app.db.models import Document, Job, Profile
from app.internal.deps import verify_internal_secret
from app.internal.schemas import ContextRequest, ContextResponse

logger = logging.getLogger("app.internal.context")

router = APIRouter(
    prefix="/internal",
    tags=["internal-context"],
    dependencies=[Depends(verify_internal_secret)],
)

_NO_PROFILE_BLOCK = (
    "The user has not uploaded a resume yet. Help them build a profile from "
    "scratch: ask about their most recent role, education, and key skills, "
    "then use update_profile_section / add_profile_item to save what they tell you."
)

_PROFILE_MODE_INSTRUCTIONS = (
    "You are in profile-enrichment mode (no specific job is in view). Compare the "
    "profile above against the good_resume.md rulebook in your system prompt: look "
    "for missing quantified impact, thin projects, an unclear target role/level, or "
    "notable gaps. Ask the user targeted, one-at-a-time questions to fill gaps, and "
    "persist every answer immediately via record_clarification, add_profile_item, or "
    "update_profile_section — don't just remember it in the conversation."
)

_JOB_MODE_INSTRUCTIONS = (
    "You are in job-tailoring mode for the job posting above. Compare the user's "
    "profile against this job's must_have/nice_to_have/keywords: identify gaps where "
    "the profile doesn't yet evidence something the job wants. Ask targeted "
    "clarifying questions and persist every answer via record_clarification, "
    "add_profile_item, or update_profile_section. Once the profile has enough to work "
    "with (or the user asks for a CV), offer to draft a tailored CV for this job via "
    "the draft_cv tool, passing this job's id shown above."
)

_JOB_NOT_FOUND_BLOCK = (
    "The referenced job could not be found for this user. Let them know and offer "
    "to help with their profile instead."
)


def _strip_namespace(conversation_id: str, user_id: str) -> str:
    prefix = f"{user_id}:"
    if conversation_id.startswith(prefix):
        conversation_id = conversation_id[len(prefix) :]
    # Strip an optional ".{n}" "new chat" generation suffix, e.g. "profile.2" -> "profile",
    # "job:abc123.3" -> "job:abc123".
    head, sep, tail = conversation_id.rpartition(".")
    if sep and tail.isdigit():
        return head
    return conversation_id


def build_context(db: Session, user_id: str, conversation_id: str) -> str:
    mode = _strip_namespace(conversation_id, user_id)

    if mode == "profile":
        profile: Profile | None = db.query(Profile).filter_by(user_id=user_id).first()
        if profile is None:
            return _NO_PROFILE_BLOCK
        return (
            f"Current master profile:\n{json.dumps(profile.data)}\n\n"
            f"{_PROFILE_MODE_INSTRUCTIONS}"
        )

    if mode.startswith("job:"):
        job_id = mode[len("job:") :]
        job: Job | None = db.query(Job).filter_by(id=job_id, user_id=user_id).first()
        if job is None:
            return _JOB_NOT_FOUND_BLOCK
        profile = db.query(Profile).filter_by(user_id=user_id).first()
        profile_block = json.dumps(profile.data) if profile is not None else "(none)"

        latest_cv: Document | None = (
            db.query(Document)
            .filter_by(user_id=user_id, job_id=job.id, type="cv")
            .order_by(Document.version.desc())
            .first()
        )
        cv_block = (
            f"A draft CV already exists for this job (version {latest_cv.version}, "
            f"created {latest_cv.created_at.isoformat()}). Calling draft_cv again creates "
            f"a new version — only do so if asked or if there's new information to reflect."
            if latest_cv is not None
            else "No CV has been drafted for this job yet."
        )

        return (
            f"Current master profile:\n{profile_block}\n\n"
            f"Job posting (id={job.id}):\n{json.dumps(job.parsed)}\n\n"
            f"{cv_block}\n\n"
            f"{_JOB_MODE_INSTRUCTIONS}"
        )

    logger.warning("internal/context: unrecognized conversation mode %r", mode)
    return "You are a job application assistant. Help the user with their profile or jobs."


@router.post("/context", response_model=ContextResponse)
def get_context(body: ContextRequest, db: Session = Depends(get_db)) -> ContextResponse:
    return ContextResponse(context=build_context(db, body.user_id, body.conversation_id))
