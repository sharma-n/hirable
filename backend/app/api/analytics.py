from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics.service import compute_analytics
from app.auth.dependencies import current_user, get_db
from app.db.models import User
from app.schemas import AnalyticsOut

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsOut)
def get_analytics(db: Session = Depends(get_db), user: User = Depends(current_user)) -> AnalyticsOut:
    return compute_analytics(db, user.id)
