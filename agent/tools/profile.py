"""Write tools over the user's master profile.

There are deliberately no read tools (get_profile / list_jobs / get_job) — the
backend injects the current profile (and, in job mode, the job posting) into the
system prompt fresh on every turn via `system_prompt_fn` (see bootstrap.py), so a
round-trip read tool would be redundant.

Handlers special-case *expected* failures (404 "no profile yet", 422 bad shape)
into a readable observation string. Genuine transport failures (backend
unreachable, DNS/connection errors, timeouts) are also caught explicitly here and
turned into a plain-language observation — agent_kit's ToolRegistry *would*
convert an uncaught exception into ToolResult(ok=False) on its own, but the raw
`str(httpx.ConnectError(...))` text is not a useful message for the model to act
on (it can't do anything about "Name or service not known"), so we give it
something actionable instead.
"""
from __future__ import annotations

from typing import Any

import httpx
from agent_kit.tools.base import Tool
from llm_kit import ToolDefinition

_NO_PROFILE_MESSAGE = "No profile found yet — the user hasn't uploaded a resume."
_UNREACHABLE_MESSAGE = (
    "error: the profile service is temporarily unreachable — tell the user their "
    "change couldn't be saved and to try again in a moment."
)

_LIST_SECTIONS = ["skills", "experience", "projects", "publications", "education", "extras"]
_ALL_UPDATE_SECTIONS = ["contact", "summary", *_LIST_SECTIONS]


def _error_detail(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("detail", resp.text))
    except Exception:
        return resp.text


async def _post(client: httpx.AsyncClient, path: str, body: dict[str, Any]) -> httpx.Response | str:
    """POST to the internal API; returns the response, or a readable error string
    in place of a raw transport exception (connection refused, DNS failure, timeout)."""
    try:
        return await client.post(path, json=body)
    except httpx.RequestError:
        return _UNREACHABLE_MESSAGE


def update_profile_section_tool(client: httpx.AsyncClient) -> Tool:
    async def handler(user_id: str, args: dict[str, Any]) -> str:
        section = args.get("section")
        if not section:
            return "error: 'section' is required"
        if "value" not in args:
            return "error: 'value' is required"
        value = args["value"]

        resp = await _post(
            client,
            "/internal/profile/update-section",
            {"user_id": user_id, "section": section, "value": value},
        )
        if isinstance(resp, str):
            return resp
        if resp.status_code == 404:
            return _NO_PROFILE_MESSAGE
        if resp.status_code == 422:
            return f"error: {_error_detail(resp)}"
        resp.raise_for_status()

        count = f" ({len(value)} items)" if isinstance(value, list) else ""
        return f"Updated '{section}'{count}."

    return Tool(
        definition=ToolDefinition(
            name="update_profile_section",
            description=(
                "Replace an entire section of the user's master profile. Use this to "
                "rewrite the summary, replace the whole skills/experience/projects/"
                "education/publications/extras list, or replace contact info. This "
                "OVERWRITES the section — to add a single item to a list section "
                "without touching existing items, use add_profile_item instead."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": _ALL_UPDATE_SECTIONS,
                        "description": "Which profile section to replace.",
                    },
                    "value": {
                        "description": (
                            "New value for the section — an object for 'contact', a "
                            "string for 'summary', or an array of item objects for "
                            "list sections."
                        ),
                    },
                },
                "required": ["section", "value"],
            },
        ),
        handler=handler,
    )


def add_profile_item_tool(client: httpx.AsyncClient) -> Tool:
    async def handler(user_id: str, args: dict[str, Any]) -> str:
        section = args.get("section")
        if not section:
            return "error: 'section' is required"
        item = args.get("item")
        if not isinstance(item, dict):
            return "error: 'item' is required and must be an object"

        resp = await _post(
            client,
            "/internal/profile/add-item",
            {"user_id": user_id, "section": section, "item": item},
        )
        if isinstance(resp, str):
            return resp
        if resp.status_code == 404:
            return _NO_PROFILE_MESSAGE
        if resp.status_code == 422:
            return f"error: {_error_detail(resp)}"
        resp.raise_for_status()
        return f"Added item to '{section}'."

    return Tool(
        definition=ToolDefinition(
            name="add_profile_item",
            description=(
                "Append a single new item to a list-type profile section (skills, "
                "experience, projects, education, publications, or extras) without "
                "removing existing items."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "section": {"type": "string", "enum": _LIST_SECTIONS},
                    "item": {
                        "type": "object",
                        "description": (
                            "The item's fields, matching the section's schema (e.g. "
                            "an experience item: company, position, start_date, "
                            "end_date, location, summary, highlights, tech)."
                        ),
                    },
                },
                "required": ["section", "item"],
            },
        ),
        handler=handler,
    )


def record_clarification_tool(client: httpx.AsyncClient) -> Tool:
    async def handler(user_id: str, args: dict[str, Any]) -> str:
        key = args.get("key")
        value = args.get("value")
        if not key or not value:
            return "error: both 'key' and 'value' are required"

        resp = await _post(
            client,
            "/internal/profile/add-item",
            {
                "user_id": user_id,
                "section": "enrichment",
                "item": {"key": key, "value": value},
            },
        )
        if isinstance(resp, str):
            return resp
        if resp.status_code == 404:
            return _NO_PROFILE_MESSAGE
        if resp.status_code == 422:
            return f"error: {_error_detail(resp)}"
        resp.raise_for_status()
        return f"Recorded clarification: {key} = {value}"

    return Tool(
        definition=ToolDefinition(
            name="record_clarification",
            description=(
                "Persist the answer to a clarifying question you asked the user, "
                "enriching their master profile for future document generation."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Short label for what was clarified, e.g. 'team_size_at_acme'.",
                    },
                    "value": {"type": "string", "description": "The user's answer."},
                },
                "required": ["key", "value"],
            },
        ),
        handler=handler,
    )
