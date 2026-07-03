"""Shared HTTP client for calling the backend's secret-gated internal API."""
from __future__ import annotations

import httpx


def build_internal_client(base_url: str, secret: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        headers={"X-Internal-Secret": secret},
        timeout=10.0,
    )
