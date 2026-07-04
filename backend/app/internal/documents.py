from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from llm_kit import LLMClient
from sqlalchemy.orm import Session

from app.auth.dependencies import get_db
from app.db.models import Job, Profile
from app.internal.deps import verify_internal_secret
from app.internal.schemas import (
    DraftCoverLetterRequest,
    DraftCoverLetterResponse,
    DraftCvRequest,
    DraftCvResponse,
)
from app.llm.deps import get_llm
from app.rendercv.service import draft_cover_letter_document, draft_cv_document

router = APIRouter(
    prefix="/internal/documents",
    tags=["internal-documents"],
    dependencies=[Depends(verify_internal_secret)],
)


def _get_job_and_profile(db: Session, user_id: str, job_id: str) -> tuple[Job, Profile]:
    job = db.query(Job).filter_by(id=job_id, user_id=user_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    profile = db.query(Profile).filter_by(user_id=user_id).first()
    if profile is None:
        raise HTTPException(
            status_code=404, detail="No profile found yet — the user hasn't uploaded a resume."
        )
    return job, profile


@router.post("/draft-cv", response_model=DraftCvResponse)
async def draft_cv(
    body: DraftCvRequest,
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
) -> DraftCvResponse:
    job, profile = _get_job_and_profile(db, body.user_id, body.job_id)
    document = await draft_cv_document(db, llm, job, profile, body.instructions)
    return DraftCvResponse(document_id=document.id, version=document.version)


@router.post("/draft-cover-letter", response_model=DraftCoverLetterResponse)
async def draft_cover_letter(
    body: DraftCoverLetterRequest,
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
) -> DraftCoverLetterResponse:
    job, profile = _get_job_and_profile(db, body.user_id, body.job_id)
    document = await draft_cover_letter_document(db, llm, job, profile, body.instructions)
    return DraftCoverLetterResponse(document_id=document.id, version=document.version)
