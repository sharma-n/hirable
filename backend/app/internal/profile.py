from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_db
from app.db.models import Profile
from app.internal.deps import verify_internal_secret
from app.internal.schemas import ProfileItemAddRequest, ProfileSectionUpdateRequest
from app.llm.schemas import (
    ContactInfo,
    EducationItem,
    EnrichmentItem,
    ExperienceItem,
    ExtrasItem,
    ProjectItem,
    PublicationItem,
    SkillItem,
)

router = APIRouter(
    prefix="/internal/profile",
    tags=["internal-profile"],
    dependencies=[Depends(verify_internal_secret)],
)

# Section name -> item model, for list-type sections.
_LIST_SECTIONS: dict[str, type[BaseModel]] = {
    "skills": SkillItem,
    "experience": ExperienceItem,
    "projects": ProjectItem,
    "publications": PublicationItem,
    "education": EducationItem,
    "extras": ExtrasItem,
    "enrichment": EnrichmentItem,
}


def _get_profile_or_404(db: Session, user_id: str) -> Profile:
    profile = db.query(Profile).filter_by(user_id=user_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="No profile found")
    return profile


@router.post("/update-section")
def update_section(body: ProfileSectionUpdateRequest, db: Session = Depends(get_db)) -> dict:
    profile = _get_profile_or_404(db, body.user_id)

    if body.section == "contact":
        try:
            validated_value: object = ContactInfo.model_validate(body.value).model_dump()
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    elif body.section == "summary":
        if not isinstance(body.value, str):
            raise HTTPException(status_code=422, detail="'summary' must be a string")
        validated_value = body.value
    elif body.section in _LIST_SECTIONS:
        if not isinstance(body.value, list):
            raise HTTPException(
                status_code=422, detail=f"'{body.section}' must be a list of items"
            )
        model = _LIST_SECTIONS[body.section]
        try:
            validated_value = [model.model_validate(item).model_dump() for item in body.value]
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        raise HTTPException(status_code=422, detail=f"Unknown section '{body.section}'")

    # Reassign a new dict object (not an in-place mutation) so SQLAlchemy's JSON
    # column change-detection fires without needing MutableDict/flag_modified.
    profile.data = {**profile.data, body.section: validated_value}
    profile.version += 1
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(profile)
    return profile.data


@router.post("/add-item")
def add_item(body: ProfileItemAddRequest, db: Session = Depends(get_db)) -> dict:
    profile = _get_profile_or_404(db, body.user_id)

    if body.section not in _LIST_SECTIONS:
        raise HTTPException(
            status_code=422, detail=f"'{body.section}' is not a list-type section"
        )
    model = _LIST_SECTIONS[body.section]
    try:
        validated_item = model.model_validate(body.item).model_dump()
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    existing_items = profile.data.get(body.section, [])
    profile.data = {**profile.data, body.section: [*existing_items, validated_item]}
    profile.version += 1
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(profile)
    return profile.data
