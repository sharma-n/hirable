"""Agent sidecar entry point.

Builds the harness_kit app from the shared config.yaml, stripping the `app:` section
that belongs to the backend before passing it to harness_kit (which rejects unknown keys).

Start with:
    uvicorn bootstrap:create_app --factory --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import httpx
import yaml
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from tools import build_tools
from tools.client import build_internal_client
from tools.context import build_system_prompt_fn

_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}")


def _expand_env(value: str) -> str:
    """Expand ``${VAR:-default}`` in a string value.

    The `app:` block is stripped out of the config before it's handed to
    harness_kit's `load_dict` (which runs its own `_interpolate_env` on the rest of
    the config) — so anything read out of `app:` here needs its own expansion,
    mirroring `backend/app/config.py`'s `_expand`.
    """

    def _sub(m: re.Match) -> str:
        var, default = m.group(1), m.group(2) or ""
        return os.environ.get(var, default)

    return _ENV_VAR_RE.sub(_sub, value)


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


def _find_good_resume() -> Path:
    # Docker: docs/ is mounted next to bootstrap.py at /app/docs (see docker-compose.yml)
    # Local dev: docs/ is at the repo root, one level above agent/
    here = Path(__file__).parent
    for candidate in (here / "docs" / "good_resume.md", here.parent / "docs" / "good_resume.md"):
        if candidate.exists():
            return candidate
    raise RuntimeError(
        "docs/good_resume.md not found. In Docker it should be mounted at /app/docs; "
        "locally it should be at <repo root>/docs/good_resume.md."
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
    from harness_kit.config.loader import load_dict
    from harness_kit.config.schema import HarnessKitConfig
    from harness_kit.service import AgentService
    from harness_kit.serving.app import create_app as agent_create_app

    config_path = _find_config()
    raw = yaml.safe_load(config_path.read_text())

    app_block = raw.get("app", {})

    # Strip backend-only keys — harness_kit rejects unknown top-level keys.
    agent_raw = {k: v for k, v in raw.items() if k != "app"}

    # M4: embed the good_resume.md rulebook into the static system prompt.
    good_resume_text = _find_good_resume().read_text()
    agent_raw["agent"]["system_prompt"] = (
        agent_raw["agent"]["system_prompt"] + "\n\n" + good_resume_text
    )

    secret = os.environ.get("AGENT_INTERNAL_SECRET", "")
    internal_base_url = _expand_env(app_block.get("internal_base_url", "http://backend:8000"))
    internal_client = build_internal_client(internal_base_url, secret)

    # M4: per-turn dynamic context (the user's profile, and — in job mode — the
    # job posting) is injected fresh on every turn rather than fetched via a
    # read tool, so the agent never needs a round trip to see its own writes.
    service = AgentService.build(
        load_dict(HarnessKitConfig, agent_raw),
        extra_tools=build_tools(internal_client),
        system_prompt_fn=build_system_prompt_fn(internal_client),
    )

    app = agent_create_app(service)
    app.add_middleware(InternalSecretMiddleware, secret=secret)
    # No explicit shutdown hook for internal_client: this Starlette version has
    # dropped both on_event and router.on_shutdown, and agent_create_app(service)
    # already owns its own lifespan internally. The client lives for the process
    # lifetime, which is fine for a single-process sidecar.

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app
