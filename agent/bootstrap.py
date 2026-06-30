"""Agent sidecar entry point.

Builds the agent_kit app from the shared config.yaml, stripping the `app:` section
that belongs to the backend before passing it to agent_kit (which rejects unknown keys).

Start with:
    uvicorn bootstrap:create_app --factory --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


def _find_config() -> Path:
    # Docker: config.yaml is mounted next to bootstrap.py at /app/config.yaml
    # Local dev: config.yaml is at the repo root, one level above agent/
    here = Path(__file__).parent
    for candidate in (here / "config.yaml", here.parent / "config.yaml"):
        if candidate.exists():
            return candidate
    raise RuntimeError(
        "config.yaml not found. In Docker it should be mounted at /app/config.yaml; "
        "locally it should be at the repo root."
    )


class InternalSecretMiddleware(BaseHTTPMiddleware):
    """Reject requests that don't carry the correct X-Internal-Secret header."""

    def __init__(self, app, secret: str) -> None:
        super().__init__(app)
        self._secret = secret

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path == "/health":
            return await call_next(request)
        if request.headers.get("X-Internal-Secret") != self._secret:
            return JSONResponse({"detail": "Forbidden"}, status_code=403)
        return await call_next(request)


def create_app():
    """ASGI factory called by uvicorn --factory."""
    from agent_kit.config.loader import load_dict
    from agent_kit.config.schema import AgentKitConfig
    from agent_kit.service import AgentService
    from agent_kit.serving.app import create_app as agent_create_app

    config_path = _find_config()
    raw = yaml.safe_load(config_path.read_text())

    # Strip backend-only keys — agent_kit rejects unknown top-level keys.
    agent_raw = {k: v for k, v in raw.items() if k != "app"}
    service = AgentService.build(load_dict(AgentKitConfig, agent_raw))

    app = agent_create_app(service)

    secret = os.environ.get("AGENT_INTERNAL_SECRET", "")
    app.add_middleware(InternalSecretMiddleware, secret=secret)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app
