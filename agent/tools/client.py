"""Shared HTTP client + POST helper for calling the backend's secret-gated internal API."""
from __future__ import annotations

from typing import Any

import httpx

UNREACHABLE_MESSAGE = (
    "error: the profile service is temporarily unreachable — tell the user their "
    "change couldn't be saved and to try again in a moment."
)


def build_internal_client(base_url: str, secret: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        headers={"X-Internal-Secret": secret},
        timeout=10.0,
    )


def error_detail(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("detail", resp.text))
    except Exception:
        return resp.text


async def post_json(client: httpx.AsyncClient, path: str, body: dict[str, Any]) -> httpx.Response | str:
    """POST to the internal API; returns the response, or a readable error string
    in place of a raw transport exception (connection refused, DNS failure, timeout)."""
    try:
        return await client.post(path, json=body)
    except httpx.RequestError:
        return UNREACHABLE_MESSAGE
