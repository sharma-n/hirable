from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator, model_validator


class SignupRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ResetPasswordRequest(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeOut(BaseModel):
    id: str
    user_id: str
    filename: str
    format: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class ProfileOut(BaseModel):
    id: str
    user_id: str
    version: int
    data: dict
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: str
    user_id: str
    source_url: str | None
    raw_text: str
    parsed: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobCreateRequest(BaseModel):
    url: str | None = None
    raw_text: str | None = None

    @model_validator(mode="after")
    def _require_url_or_raw_text(self) -> "JobCreateRequest":
        if not self.url and not self.raw_text:
            raise ValueError("Provide at least one of 'url' or 'raw_text'")
        return self
