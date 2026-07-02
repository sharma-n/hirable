from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_db, require_admin
from app.auth.password import hash_password
from app.auth.sessions import delete_user_sessions
from app.db.models import User
from app.files import delete_user_uploads
from app.schemas import ResetPasswordRequest, UserOut

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[User]:
    return db.query(User).order_by(User.created_at).all()


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> None:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Guard: don't delete the last admin
    if target.role == "admin":
        admin_count = db.query(User).filter(User.role == "admin").count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last admin")

    delete_user_uploads(user_id)
    db.delete(target)
    db.commit()


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: str,
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict:
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target.password_hash = hash_password(body.new_password)
    delete_user_sessions(db, user_id)
    db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/disable")
def disable_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")

    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target.is_active = False
    delete_user_sessions(db, user_id)
    db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/enable")
def enable_user(
    user_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict:
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target.is_active = True
    db.commit()
    return {"ok": True}
