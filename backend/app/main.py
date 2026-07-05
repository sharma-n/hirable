from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.applications import router as applications_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.jobs import router as jobs_router
from app.api.profile import router as profile_router
from app.applications.scheduler import build_scheduler, run_automation_once
from app.applications.service import backfill_applications
from app.db.engine import SessionLocal
from app.db.migrate import run_migrations
from app.internal import router as internal_router
from app.llm.client import build_llm

# Attach our handlers to uvicorn's stream so `app.*` loggers surface in the
# server terminal with a consistent format. `force=True` reclaims the root from
# any earlier basicConfig; uvicorn's own access/error loggers are untouched.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)


def _under_pytest() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    app.state.llm = build_llm()
    app.state.scheduler = None
    # The scheduler/backfill below call SessionLocal() directly (bypassing
    # FastAPI's get_db dependency), so they always hit the real on-disk
    # SQLite file — tests override get_db with an in-memory session, which
    # this can't see. Skip them under pytest to avoid mutating a developer's
    # real dev DB (and spinning up a background thread) on every test run.
    if not _under_pytest():
        db = SessionLocal()
        try:
            backfill_applications(db)
        finally:
            db.close()
        app.state.scheduler = build_scheduler()
        app.state.scheduler.start()
        run_automation_once()
    try:
        yield
    finally:
        if app.state.scheduler is not None:
            app.state.scheduler.shutdown()
        await app.state.llm.aclose()


app = FastAPI(title="hirable", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(chat_router)
app.include_router(profile_router)
app.include_router(jobs_router)
app.include_router(documents_router)
app.include_router(applications_router)
app.include_router(internal_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
