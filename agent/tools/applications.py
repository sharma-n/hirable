"""list_application_status / change_application_status tools (M7).

Both are job-scoped (take an explicit job_id, same reasoning as draft_cv —
the agent already sees the job's id in the job-mode context block). Unlike
the profile tools, applications data isn't injected into the system prompt
every turn (SPEC §6.1's per-turn injection only covers profile/job), so
list_application_status is a genuine read tool here — the one exception to
the "write-only tools" philosophy, justified because there's no other channel
for the agent to learn an application's current stage.
"""
from __future__ import annotations

from typing import Any

import httpx
from harness_kit.tools.base import Tool
from llm_kit import ToolDefinition

from .client import error_detail, post_json

_NO_JOB_MESSAGE = "That job could not be found."

_STAGES = (
    "Draft",
    "Applied",
    "Recruiter Screen",
    "Technical",
    "Onsite",
    "Offer",
    "Accepted",
    "Declined",
    "Rejected",
    "Stale",
)


def list_application_status_tool(client: httpx.AsyncClient) -> Tool:
    async def handler(user_id: str, args: dict[str, Any]) -> str:
        job_id = args.get("job_id")
        if not job_id:
            return "error: 'job_id' is required"

        resp = await post_json(
            client, "/internal/applications/status", {"user_id": user_id, "job_id": job_id}
        )
        if isinstance(resp, str):
            return resp
        if resp.status_code == 404:
            return _NO_JOB_MESSAGE
        resp.raise_for_status()
        return resp.json()["summary"]

    return Tool(
        definition=ToolDefinition(
            name="list_application_status",
            description=(
                "Look up the current application-tracking status for a specific job: "
                "stage, submission date, next action, and whether documents have been "
                "finalized. Use this to answer questions like 'what's the status of my "
                "application for this role?'."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "The job's id, as shown in the context above (Job posting (id=...)).",
                    },
                },
                "required": ["job_id"],
            },
        ),
        handler=handler,
    )


def change_application_status_tool(client: httpx.AsyncClient) -> Tool:
    async def handler(user_id: str, args: dict[str, Any]) -> str:
        job_id = args.get("job_id")
        stage = args.get("stage")
        if not job_id:
            return "error: 'job_id' is required"
        if not stage:
            return "error: 'stage' is required"

        resp = await post_json(
            client,
            "/internal/applications/set-stage",
            {"user_id": user_id, "job_id": job_id, "stage": stage},
        )
        if isinstance(resp, str):
            return resp
        if resp.status_code == 404:
            return _NO_JOB_MESSAGE
        if resp.status_code == 422:
            return f"error: {error_detail(resp)}"
        resp.raise_for_status()
        body = resp.json()
        return f"Application stage updated. {body['summary']}"

    return Tool(
        definition=ToolDefinition(
            name="change_application_status",
            description=(
                "Move a job's application to a new stage in the tracking pipeline "
                f"(one of: {', '.join(_STAGES)}). Moving to 'Applied' for the first time "
                "automatically finalizes the latest CV and cover-letter drafts as the "
                "submitted documents. Only call this when the user explicitly says they "
                "applied, heard back, or want to update/correct their tracking status — "
                "never guess or advance a stage on your own."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "The job's id, as shown in the context above (Job posting (id=...)).",
                    },
                    "stage": {
                        "type": "string",
                        "description": "The new stage.",
                        "enum": list(_STAGES),
                    },
                },
                "required": ["job_id", "stage"],
            },
        ),
        handler=handler,
    )
