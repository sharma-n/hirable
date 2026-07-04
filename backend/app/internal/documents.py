from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from llm_kit import LLMClient
from sqlalchemy.orm import Session

from app.auth.dependencies import get_db
from app.db.models import Job, Profile
from app.internal.deps import verify_internal_secret
from app.internal.schemas import DraftCvRequest, DraftCvResponse
from app.llm.deps import get_llm
from app.rendercv.service import draft_cv_document

router = APIRouter(
    prefix="/internal/documents",
    tags=["internal-documents"],
    dependencies=[Depends(verify_internal_secret)],
)


@router.post("/draft-cv", response_model=DraftCvResponse)
async def draft_cv(
    body: DraftCvRequest,
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
) -> DraftCvResponse:
    job = db.query(Job).filter_by(id=body.job_id, user_id=body.user_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    profile = db.query(Profile).filter_by(user_id=body.user_id).first()
    if profile is None:
        raise HTTPException(
            status_code=404, detail="No profile found yet — the user hasn't uploaded a resume."
        )

    document = await draft_cv_document(db, llm, job, profile, body.instructions)
    return DraftCvResponse(document_id=document.id, version=document.version)
