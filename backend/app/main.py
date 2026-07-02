from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.profile import router as profile_router
from app.db.migrate import run_migrations
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    app.state.llm = build_llm()
    from docling.document_converter import DocumentConverter
    app.state.docling_converter = DocumentConverter()
    try:
        yield
    finally:
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


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
