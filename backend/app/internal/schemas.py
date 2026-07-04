from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ContextRequest(BaseModel):
    user_id: str
    conversation_id: str


class ContextResponse(BaseModel):
    context: str


class ProfileSectionUpdateRequest(BaseModel):
    user_id: str
    section: str
    value: Any


class ProfileItemAddRequest(BaseModel):
    user_id: str
    section: str
    item: dict[str, Any]


class DraftCvRequest(BaseModel):
    user_id: str
    job_id: str
    instructions: str | None = None


class DraftCvResponse(BaseModel):
    document_id: str
    version: int
