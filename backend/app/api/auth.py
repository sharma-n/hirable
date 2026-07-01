from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import current_user, get_db
from app.auth.password import hash_password, verify_password
from app.auth.sessions import (
    clear_session_cookie,
    create_session,
    delete_session,
    set_session_cookie,
    COOKIE_NAME,
)
from app.db.models import User
from app.schemas import LoginRequest, SignupRequest, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=UserOut, status_code=201)
def signup(body: SignupRequest, response: Response, db: Session = Depends(get_db)) -> User:
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    is_first = db.query(User).count() == 0
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        role="admin" if is_first else "user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_session(db, user.id)
    set_session_cookie(response, token)
    return user


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(user.password_hash, body.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_session(db, user.id)
    set_session_cookie(response, token)
    return user


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        delete_session(db, token)
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user
