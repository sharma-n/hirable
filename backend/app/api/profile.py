from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from llm_kit import LLMClient
from sqlalchemy.orm import Session

from app.auth.dependencies import current_user, get_db
from app.db.models import Profile, Resume, User
from app.files import delete_user_uploads, save_upload
from app.llm.deps import get_llm
from app.llm.schemas import ProfileModel
from app.parsing.deps import get_docling_converter
from app.parsing.extract import extract_text
from app.parsing.profile import parse_resume
from app.schemas import ProfileOut, ResumeOut

logger = logging.getLogger("app.profile")

router = APIRouter(prefix="/api/profile", tags=["profile"])

_ALLOWED_EXTENSIONS = {"pdf", "docx", "tex"}


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@router.post("/resume", response_model=ProfileOut, status_code=201)
async def upload_resume(
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    llm: LLMClient = Depends(get_llm),
    converter=Depends(get_docling_converter),
) -> Profile:
    ext = _ext(file.filename or "")
    if ext not in _ALLOWED_EXTENSIONS:
        logger.warning(
            "resume upload rejected: user=%s filename=%r unsupported ext=%r",
            user.id, file.filename, ext,
        )
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '.{ext}'. Allowed: pdf, docx, tex",
        )

    started = time.perf_counter()

    def _elapsed_ms() -> int:
        return round((time.perf_counter() - started) * 1000)

    data = await file.read()
    logger.info(
        "resume upload received: user=%s filename=%r fmt=%s size=%d bytes",
        user.id, file.filename, ext, len(data),
    )

    # Stage 1 — extract raw text (docling for pdf/docx, strip for tex).
    raw_text = extract_text(data, ext, converter)
    logger.info(
        "resume text extracted: user=%s chars=%d [%dms]",
        user.id, len(raw_text), _elapsed_ms(),
    )

    # Stage 2 — persist the uploaded file to disk.
    save_upload(user.id, data, ext)
    logger.info("resume file saved to disk: user=%s [%dms]", user.id, _elapsed_ms())

    # Stage 3 — record the Resume row (audit trail).
    resume_row = Resume(
        user_id=user.id,
        filename=file.filename or f"resume.{ext}",
        format=ext,
        raw_text=raw_text,
    )
    db.add(resume_row)

    # Stage 4 — parse the master profile via the LLM (slowest stage).
    logger.info("resume LLM parse started: user=%s", user.id)
    profile_model: ProfileModel = await parse_resume(llm, raw_text)
    profile_data = profile_model.model_dump()
    logger.info(
        "resume LLM parse complete: user=%s experience=%d education=%d skills=%d [%dms]",
        user.id,
        len(profile_model.experience),
        len(profile_model.education),
        len(profile_model.skills),
        _elapsed_ms(),
    )

    # Stage 5 — upsert the single Profile row for this user.
    existing: Profile | None = db.query(Profile).filter_by(user_id=user.id).first()
    if existing is None:
        profile_row = Profile(
            user_id=user.id,
            version=1,
            data=profile_data,
        )
        db.add(profile_row)
    else:
        existing.data = profile_data
        existing.version += 1
        existing.updated_at = datetime.now(timezone.utc)
        profile_row = existing

    db.commit()
    db.refresh(profile_row)
    logger.info(
        "resume upload complete: user=%s profile_version=%d total=%dms",
        user.id, profile_row.version, _elapsed_ms(),
    )
    return profile_row


@router.get("", status_code=200)
def get_profile(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ProfileOut | None:
    profile: Profile | None = db.query(Profile).filter_by(user_id=user.id).first()
    if profile is None:
        response.status_code = 204
        return None
    return ProfileOut.model_validate(profile)


@router.put("", response_model=ProfileOut)
def update_profile(
    body: ProfileModel,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Profile:
    profile: Profile | None = db.query(Profile).filter_by(user_id=user.id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="No profile found. Upload a resume first.")
    profile.data = body.model_dump()
    profile.version += 1
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(profile)
    return profile
