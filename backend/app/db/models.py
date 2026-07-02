from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    sessions: Mapped[list[Session]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )
    resumes: Mapped[list[Resume]] = relationship(
        "Resume", back_populates="user", cascade="all, delete-orphan"
    )
    profile: Mapped[Profile | None] = relationship(
        "Profile", back_populates="user", cascade="all, delete-orphan", uselist=False
    )


class Session(Base):
    __tablename__ = "sessions"

    # Stores SHA-256 hash of the raw token; raw token lives only in the cookie
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    user: Mapped[User] = relationship("User", back_populates="sessions")


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    format: Mapped[str] = mapped_column(String, nullable=False)  # pdf | docx | tex
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    user: Mapped[User] = relationship("User", back_populates="resumes")


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    user: Mapped[User] = relationship("User", back_populates="profile")
