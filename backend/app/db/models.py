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
    jobs: Mapped[list[Job]] = relationship(
        "Job", back_populates="user", cascade="all, delete-orphan"
    )
    documents: Mapped[list[Document]] = relationship(
        "Document", back_populates="user", cascade="all, delete-orphan"
    )
    profile_versions: Mapped[list[ProfileVersion]] = relationship(
        "ProfileVersion", back_populates="user", cascade="all, delete-orphan"
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


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    user: Mapped[User] = relationship("User", back_populates="jobs")
    documents: Mapped[list[Document]] = relationship(
        "Document", back_populates="job", cascade="all, delete-orphan"
    )


class Document(Base):
    """A generated CV/cover-letter draft. Versions are append-only rows — never
    mutated in place — so a finalized application (M7) can snapshot the exact
    document that was submitted even after later edits. Only the source text
    (RenderCV YAML) is persisted; PDFs are compiled on demand and never stored
    on disk (see backend/app/rendercv/compile.py)."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(
        String, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String, nullable=False)  # "cv" | "cover_letter"
    source_format: Mapped[str] = mapped_column(String, nullable=False, default="rendercv_yaml")
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_finalized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    user: Mapped[User] = relationship("User", back_populates="documents")
    job: Mapped[Job] = relationship("Job", back_populates="documents")


class ProfileVersion(Base):
    """Pre-change snapshot of a user's profile data, for undo/history.

    Snapshots capture the profile's state *before* a write is applied, so
    "restore version N" reads naturally as "go back to how things were right
    before that change." Agent-write bursts within a debounce window coalesce
    into a single snapshot (see backend/app/db/profile_history.py); user saves
    always snapshot immediately. Pruned to a configurable max per user.
    """

    __tablename__ = "profile_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)  # "user" | "agent" | "restore"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    user: Mapped[User] = relationship("User", back_populates="profile_versions")
