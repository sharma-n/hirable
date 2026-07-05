from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.applications.service import transition_stage
from app.applications.stages import STAGES
from app.auth.dependencies import current_user, get_db
from app.db.models import Application, User
from app.schemas import (
    ApplicationDetailOut,
    ApplicationDocumentOut,
    ApplicationListItemOut,
    ApplicationPatchRequest,
    ApplicationStageEventOut,
    ApplicationSubmitResult,
)

router = APIRouter(prefix="/api/applications", tags=["applications"])


def _get_application_or_404(db: Session, application_id: str, user_id: str) -> Application:
    application = db.query(Application).filter_by(id=application_id, user_id=user_id).first()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def _to_list_item(application: Application) -> ApplicationListItemOut:
    parsed = application.job.parsed
    return ApplicationListItemOut(
        id=application.id,
        job_id=application.job_id,
        stage=application.stage,
        company=parsed.get("company", ""),
        title=parsed.get("title", ""),
        submitted_at=application.submitted_at,
        last_activity_at=application.last_activity_at,
        auto_stale_at=application.auto_stale_at,
        next_action=application.next_action,
    )


def _to_detail(application: Application) -> ApplicationDetailOut:
    item = _to_list_item(application)
    return ApplicationDetailOut(
        **item.model_dump(),
        notes=application.notes,
        events=[ApplicationStageEventOut.model_validate(e) for e in application.events],
        documents=[ApplicationDocumentOut.model_validate(d) for d in application.documents],
    )


@router.get("", response_model=list[ApplicationListItemOut])
def list_applications(
    job_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[ApplicationListItemOut]:
    query = db.query(Application).filter_by(user_id=user.id)
    if job_id is not None:
        query = query.filter_by(job_id=job_id)
    applications = query.order_by(Application.updated_at.desc()).all()
    return [_to_list_item(a) for a in applications]


@router.get("/{application_id}", response_model=ApplicationDetailOut)
def get_application(
    application_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> ApplicationDetailOut:
    application = _get_application_or_404(db, application_id, user.id)
    return _to_detail(application)


@router.patch("/{application_id}", response_model=ApplicationDetailOut)
def patch_application(
    application_id: str,
    body: ApplicationPatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ApplicationDetailOut:
    application = _get_application_or_404(db, application_id, user.id)

    if body.stage is not None:
        if body.stage not in STAGES:
            raise HTTPException(
                status_code=422, detail=f"Invalid stage — valid stages are: {', '.join(STAGES)}"
            )
        application, _missing_docs = transition_stage(db, application, body.stage, actor="user")

    if body.next_action is not None:
        application.next_action = body.next_action
    if body.notes is not None:
        application.notes = body.notes
    if body.next_action is not None or body.notes is not None:
        db.commit()
        db.refresh(application)

    return _to_detail(application)


@router.post("/{application_id}/submit", response_model=ApplicationSubmitResult)
def submit_application(
    application_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> ApplicationSubmitResult:
    """Canonical submit sugar for stage -> Applied: snapshots the latest CV +
    cover-letter Document versions (see transition_stage/finalize_documents).
    ``missing_documents`` lists any doc_type that couldn't be finalized
    because nothing has been drafted for this job yet."""
    application = _get_application_or_404(db, application_id, user.id)
    application, missing_docs = transition_stage(db, application, "Applied", actor="user")
    return ApplicationSubmitResult(application=_to_detail(application), missing_documents=missing_docs)
