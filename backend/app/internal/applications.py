from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.applications.service import get_or_create_application, transition_stage
from app.applications.stages import STAGES
from app.auth.dependencies import get_db
from app.db.models import Application, Job
from app.internal.deps import verify_internal_secret
from app.internal.schemas import (
    ApplicationSetStageRequest,
    ApplicationSetStageResponse,
    ApplicationStatusRequest,
    ApplicationStatusResponse,
)

router = APIRouter(
    prefix="/internal/applications",
    tags=["internal-applications"],
    dependencies=[Depends(verify_internal_secret)],
)


def _get_job_or_404(db: Session, user_id: str, job_id: str) -> Job:
    job = db.query(Job).filter_by(id=job_id, user_id=user_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _summarize(application: Application, job: Job) -> str:
    parsed = job.parsed
    company = parsed.get("company") or "this company"
    title = parsed.get("title") or "this role"
    parts = [f"Application for {title} at {company} is at stage: {application.stage}."]
    if application.submitted_at is not None:
        parts.append(f"Submitted on {application.submitted_at.date().isoformat()}.")
    if application.next_action:
        parts.append(f"Next action: {application.next_action}.")
    finalized_types = {d.doc_type for d in application.documents}
    if finalized_types:
        parts.append(f"Finalized documents on file: {', '.join(sorted(finalized_types))}.")
    else:
        parts.append("No documents have been finalized for this application yet.")
    return " ".join(parts)


@router.post("/status", response_model=ApplicationStatusResponse)
def get_status(body: ApplicationStatusRequest, db: Session = Depends(get_db)) -> ApplicationStatusResponse:
    job = _get_job_or_404(db, body.user_id, body.job_id)
    application = get_or_create_application(db, job)
    return ApplicationStatusResponse(summary=_summarize(application, job))


@router.post("/set-stage", response_model=ApplicationSetStageResponse)
def set_stage(
    body: ApplicationSetStageRequest, db: Session = Depends(get_db)
) -> ApplicationSetStageResponse:
    if body.stage not in STAGES:
        raise HTTPException(
            status_code=422, detail=f"Invalid stage — valid stages are: {', '.join(STAGES)}"
        )
    job = _get_job_or_404(db, body.user_id, body.job_id)
    application = get_or_create_application(db, job)
    application, _missing_docs = transition_stage(db, application, body.stage, actor="agent")
    return ApplicationSetStageResponse(stage=application.stage, summary=_summarize(application, job))
