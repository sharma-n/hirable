from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from llm_kit import LLMClient
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.applications.service import get_or_create_application
from app.auth.dependencies import current_user, get_db
from app.db.models import Job, User
from app.llm.deps import get_llm
from app.llm.schemas import JobModel
from app.parsing.jobs import fetch_job_text, parse_job
from app.schemas import JobCreateRequest, JobOut

logger = logging.getLogger("app.jobs")

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobCreateResult(BaseModel):
    needs_paste: bool = False
    job: JobOut | None = None


@router.post("", response_model=JobCreateResult, status_code=201)
async def add_job(
    body: JobCreateRequest,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    llm: LLMClient = Depends(get_llm),
) -> JobCreateResult:
    raw_text = body.raw_text
    if not raw_text:
        assert body.url  # guaranteed by JobCreateRequest's validator
        logger.info("job fetch started: user=%s url=%s", user.id, body.url)
        fetched = fetch_job_text(body.url)
        if fetched is None:
            response.status_code = 200
            return JobCreateResult(needs_paste=True, job=None)
        raw_text = fetched

    parsed: JobModel = await parse_job(llm, raw_text)
    job_row = Job(
        user_id=user.id,
        source_url=body.url,
        raw_text=raw_text,
        parsed=parsed.model_dump(),
    )
    db.add(job_row)
    db.commit()
    db.refresh(job_row)
    get_or_create_application(db, job_row)
    logger.info(
        "job created: user=%s job=%s company=%r title=%r",
        user.id, job_row.id, parsed.company, parsed.title,
    )
    return JobCreateResult(needs_paste=False, job=JobOut.model_validate(job_row))


@router.get("", response_model=list[JobOut])
def list_jobs(db: Session = Depends(get_db), user: User = Depends(current_user)) -> list[Job]:
    return db.query(Job).filter_by(user_id=user.id).order_by(Job.created_at.desc()).all()


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> Job:
    job = db.query(Job).filter_by(id=job_id, user_id=user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.put("/{job_id}", response_model=JobOut)
def update_job(
    job_id: str,
    body: JobModel,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Job:
    job = db.query(Job).filter_by(id=job_id, user_id=user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    job.parsed = body.model_dump()
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204)
def delete_job(
    job_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> None:
    job = db.query(Job).filter_by(id=job_id, user_id=user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
