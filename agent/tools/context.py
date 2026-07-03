"""Per-turn dynamic system-prompt context (agent_kit's `system_prompt_fn` hook).

Fetches the user's current profile (and, in job mode, the job posting) from the
backend fresh on every turn, so the agent always sees its own prior writes without
needing a read tool.
"""
from __future__ import annotations

from typing import Awaitable, Callable

import httpx


def build_system_prompt_fn(client: httpx.AsyncClient) -> Callable[[str, str], Awaitable[str]]:
    async def system_prompt_fn(user_id: str, conversation_id: str) -> str:
        try:
            resp = await client.post(
                "/internal/context",
                json={"user_id": user_id, "conversation_id": conversation_id},
            )
            resp.raise_for_status()
            return resp.json().get("context", "")
        except Exception:
            # A turn with missing context beats a crashed turn.
            return ""

    return system_prompt_fn
