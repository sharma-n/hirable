from fastapi import APIRouter

from app.internal.context import router as context_router
from app.internal.documents import router as documents_router
from app.internal.profile import router as profile_router

router = APIRouter()
router.include_router(context_router)
router.include_router(profile_router)
router.include_router(documents_router)
