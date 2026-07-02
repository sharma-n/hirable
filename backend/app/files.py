from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from app.db.engine import _DATA_DIR

_UPLOADS_DIR = _DATA_DIR / "uploads"


def user_upload_dir(user_id: str) -> Path:
    d = _UPLOADS_DIR / user_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_upload(user_id: str, data: bytes, ext: str) -> Path:
    """Write bytes to <uploads>/<user_id>/<uuid>.<ext> and return the path."""
    dest = user_upload_dir(user_id) / f"{uuid.uuid4()}.{ext}"
    dest.write_bytes(data)
    return dest


def delete_user_uploads(user_id: str) -> None:
    """Remove all uploaded files for a user. Safe to call even if dir doesn't exist."""
    d = _UPLOADS_DIR / user_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
