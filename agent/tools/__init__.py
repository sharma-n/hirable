"""Custom hirable tool definitions.

Each tool calls the backend internal API with X-Internal-Secret + trusted user_id.
Write-only by design — there are no get_profile/list_jobs/get_job read tools; the
current profile (and job, in job mode) is injected into the system prompt fresh on
every turn via `system_prompt_fn` (see bootstrap.py).
"""
from __future__ import annotations

import httpx
from agent_kit.tools.base import Tool

from .applications import change_application_status_tool, list_application_status_tool
from .documents import draft_cover_letter_tool, draft_cv_tool
from .profile import (
    add_profile_item_tool,
    record_clarification_tool,
    update_profile_section_tool,
)

TOOL_NAMES = [
    "update_profile_section",
    "add_profile_item",
    "record_clarification",
    "draft_cv",
    "draft_cover_letter",
    "list_application_status",
    "change_application_status",
]


def build_tools(client: httpx.AsyncClient) -> list[Tool]:
    return [
        update_profile_section_tool(client),
        add_profile_item_tool(client),
        record_clarification_tool(client),
        draft_cv_tool(client),
        draft_cover_letter_tool(client),
        list_application_status_tool(client),
        change_application_status_tool(client),
    ]
