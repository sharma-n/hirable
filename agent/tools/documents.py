"""draft_cv tool — generates a tailored CV for a job.

Unlike the profile write tools, this doesn't hand a value back for the model
to see — it triggers backend-side tailoring (LLM call) + RenderCV YAML
assembly + persistence, then reports a short summary. The job-detail page's
CV panel refetches its documents on this tool's tool_result frame; the agent
never needs to see the generated YAML itself (write-only philosophy, same as
the profile tools — see bootstrap.py).
"""
from __future__ import annotations

from typing import Any

import httpx
from harness_kit.tools.base import Tool
from llm_kit import ToolDefinition

from .client import error_detail, post_json

_NO_JOB_MESSAGE = "That job could not be found."
_NO_PROFILE_MESSAGE = "No profile found yet — the user hasn't uploaded a resume."


def draft_cv_tool(client: httpx.AsyncClient) -> Tool:
    async def handler(user_id: str, args: dict[str, Any]) -> str:
        job_id = args.get("job_id")
        if not job_id:
            return "error: 'job_id' is required"
        instructions = args.get("instructions")

        resp = await post_json(
            client,
            "/internal/documents/draft-cv",
            {"user_id": user_id, "job_id": job_id, "instructions": instructions},
        )
        if isinstance(resp, str):
            return resp
        if resp.status_code == 404:
            detail = error_detail(resp)
            return _NO_PROFILE_MESSAGE if "resume" in detail.lower() else _NO_JOB_MESSAGE
        if resp.status_code == 422:
            return f"error: {error_detail(resp)}"
        resp.raise_for_status()
        body = resp.json()
        return (
            f"Draft CV v{body['version']} created — it's now in the CV panel on the "
            "job page for the user to review, edit, and compile."
        )

    return Tool(
        definition=ToolDefinition(
            name="draft_cv",
            description=(
                "Generate a tailored CV (RenderCV YAML) for a specific job — selects and "
                "rewords the most relevant profile content for that role, then saves it as "
                "a new document version. Creates a new version each time it's called, so "
                "only call it when asked or when there's meaningfully new information to "
                "reflect (a CV panel already shows any prior draft)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "The job's id, as shown in the context above (Job posting (id=...)).",
                    },
                    "instructions": {
                        "type": "string",
                        "description": "Optional emphasis from the user, e.g. 'focus on my Go experience'.",
                    },
                },
                "required": ["job_id"],
            },
        ),
        handler=handler,
    )


def draft_cover_letter_tool(client: httpx.AsyncClient) -> Tool:
    async def handler(user_id: str, args: dict[str, Any]) -> str:
        job_id = args.get("job_id")
        if not job_id:
            return "error: 'job_id' is required"
        instructions = args.get("instructions")

        resp = await post_json(
            client,
            "/internal/documents/draft-cover-letter",
            {"user_id": user_id, "job_id": job_id, "instructions": instructions},
        )
        if isinstance(resp, str):
            return resp
        if resp.status_code == 404:
            detail = error_detail(resp)
            return _NO_PROFILE_MESSAGE if "resume" in detail.lower() else _NO_JOB_MESSAGE
        if resp.status_code == 422:
            return f"error: {error_detail(resp)}"
        resp.raise_for_status()
        body = resp.json()
        return (
            f"Draft cover letter v{body['version']} created — it's now in the Cover letter "
            "panel on the job page for the user to review, edit, and compile."
        )

    return Tool(
        definition=ToolDefinition(
            name="draft_cover_letter",
            description=(
                "Generate a tailored cover letter for a specific job — a short, "
                "personalized letter tying the candidate's real experience to the job's "
                "requirements, then saves it as a new document version. Per the resume "
                "rulebook, cover letters mostly help at small/mid-size companies (big tech "
                "rarely reads them) — mention that if relevant, but generate one whenever "
                "asked. Creates a new version each time it's called, so only call it when "
                "asked or when there's meaningfully new information to reflect."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "The job's id, as shown in the context above (Job posting (id=...)).",
                    },
                    "instructions": {
                        "type": "string",
                        "description": "Optional emphasis from the user, e.g. 'mention my open-source work'.",
                    },
                },
                "required": ["job_id"],
            },
        ),
        handler=handler,
    )
