from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}")


def _expand(value: Any) -> Any:
    """Recursively expand ${VAR:-default} in string values."""
    if isinstance(value, str):
        def _sub(m: re.Match) -> str:
            var, default = m.group(1), m.group(2) or ""
            return os.environ.get(var, default)
        return _ENV_VAR_RE.sub(_sub, value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


def _find_config() -> Path:
    # Docker: /app/config.yaml (mounted), two levels up from /app/app/config.py
    # Local:  repo root config.yaml, three levels up from backend/app/config.py
    here = Path(__file__).parent
    for candidate in (here.parent / "config.yaml", here.parent.parent / "config.yaml"):
        if candidate.exists():
            return candidate
    raise RuntimeError(
        "config.yaml not found. In Docker it should be mounted at /app/config.yaml; "
        "locally it should be at the repo root."
    )


@lru_cache(maxsize=1)
def get_config() -> dict:
    raw = _find_config().read_text()
    return _expand(yaml.safe_load(raw))


def app_config() -> dict:
    return get_config().get("app", {})


def agent_base_url() -> str:
    return app_config().get("agent_base_url", "http://agent:8000")
