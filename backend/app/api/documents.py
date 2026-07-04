from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from llm_kit import LLMClient
from sqlalchemy.orm import Session

from app.auth.dependencies import current_user, get_db
from app.db.models import Document, Job, Profile, User
from app.llm.deps import get_llm
from app.rendercv.compile import CompileError, compile_pdf
from app.rendercv.service import draft_cv_document
from app.schemas import (
    DocumentCompileRequest,
    DocumentDraftRequest,
    DocumentListItemOut,
    DocumentOut,
    DocumentUpdateRequest,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _get_job_or_404(db: Session, job_id: str, user_id: str) -> Job:
    job = db.query(Job).filter_by(id=job_id, user_id=user_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _get_document_or_404(db: Session, document_id: str, user_id: str) -> Document:
    document = db.query(Document).filter_by(id=document_id, user_id=user_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.post("/draft", response_model=DocumentOut, status_code=201)
async def draft_cv(
    body: DocumentDraftRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    llm: LLMClient = Depends(get_llm),
) -> Document:
    job = _get_job_or_404(db, body.job_id, user.id)
    profile: Profile | None = db.query(Profile).filter_by(user_id=user.id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="No profile found. Upload a resume first.")
    return await draft_cv_document(db, llm, job, profile, body.instructions)


@router.get("", response_model=list[DocumentListItemOut])
def list_documents(
    job_id: str,
    type: str = "cv",
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[Document]:
    _get_job_or_404(db, job_id, user.id)
    return (
        db.query(Document)
        .filter_by(user_id=user.id, job_id=job_id, type=type)
        .order_by(Document.version.desc())
        .all()
    )


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> Document:
    return _get_document_or_404(db, document_id, user.id)


@router.put("/{document_id}", response_model=DocumentOut)
def save_document(
    document_id: str,
    body: DocumentUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Document:
    """Creates a new version row rather than mutating in place — see Document's
    docstring: versions are append-only so a finalized application (M7) can
    snapshot the exact document that was submitted even after later edits."""
    existing = _get_document_or_404(db, document_id, user.id)
    new_version = Document(
        user_id=existing.user_id,
        job_id=existing.job_id,
        type=existing.type,
        source_text=body.source_text,
        version=existing.version + 1,
    )
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    return new_version


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> None:
    document = _get_document_or_404(db, document_id, user.id)
    db.delete(document)
    db.commit()


@router.post("/compile")
def compile_document(
    body: DocumentCompileRequest, _user: User = Depends(current_user)
) -> Response:
    """Stateless compile-preview: takes source text directly (not a document id),
    so it covers both previewing unsaved editor changes and viewing a saved
    version — the frontend always has the source text in hand either way. No
    PDF is ever persisted (see Document's docstring)."""
    try:
        pdf_bytes = compile_pdf(body.source_text)
    except CompileError as exc:
        raise HTTPException(
            status_code=422, detail={"stage": exc.stage, "errors": exc.errors}
        ) from exc
    return Response(content=pdf_bytes, media_type="application/pdf")
