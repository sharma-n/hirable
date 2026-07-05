"""Unit tests for the hirable agent's tool handlers and system_prompt_fn.

These call the handler functions directly against a mocked HTTP transport (no
real backend, no agent_kit service/registry involved) — they verify the
right request is sent and that 200/404/422 responses map to the expected
observation strings.
"""
from __future__ import annotations

import json

import httpx
import pytest

from tools.applications import change_application_status_tool, list_application_status_tool
from tools.context import build_system_prompt_fn
from tools.documents import draft_cover_letter_tool, draft_cv_tool
from tools.profile import (
    add_profile_item_tool,
    record_clarification_tool,
    update_profile_section_tool,
)


def _client_with_handler(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(base_url="http://backend:8000", transport=transport)


@pytest.mark.asyncio
class TestUpdateProfileSectionTool:
    async def test_success_returns_confirmation_with_count(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"skills": [{"label": "x", "details": "y"}]})

        client = _client_with_handler(handler)
        tool = update_profile_section_tool(client)
        result = await tool.handler(
            "user-1", {"section": "skills", "value": [{"label": "x", "details": "y"}]}
        )

        assert seen["url"] == "http://backend:8000/internal/profile/update-section"
        assert seen["body"] == {
            "user_id": "user-1",
            "section": "skills",
            "value": [{"label": "x", "details": "y"}],
        }
        assert "Updated 'skills' (1 items)" in result

    async def test_scalar_section_no_count_suffix(self):
        client = _client_with_handler(lambda r: httpx.Response(200, json={"summary": "hi"}))
        tool = update_profile_section_tool(client)
        result = await tool.handler("user-1", {"section": "summary", "value": "hi"})
        assert result == "Updated 'summary'."

    async def test_no_profile_returns_friendly_message(self):
        client = _client_with_handler(lambda r: httpx.Response(404, json={"detail": "No profile found"}))
        tool = update_profile_section_tool(client)
        result = await tool.handler("user-1", {"section": "summary", "value": "hi"})
        assert "hasn't uploaded a resume" in result

    async def test_validation_error_returns_error_string(self):
        client = _client_with_handler(
            lambda r: httpx.Response(422, json={"detail": "bad shape"})
        )
        tool = update_profile_section_tool(client)
        result = await tool.handler("user-1", {"section": "experience", "value": "not-a-list"})
        assert result == "error: bad shape"

    async def test_missing_section_returns_error_without_http_call(self):
        client = _client_with_handler(lambda r: httpx.Response(500))
        tool = update_profile_section_tool(client)
        result = await tool.handler("user-1", {"value": "hi"})
        assert result == "error: 'section' is required"

    async def test_missing_value_returns_error_without_http_call(self):
        client = _client_with_handler(lambda r: httpx.Response(500))
        tool = update_profile_section_tool(client)
        result = await tool.handler("user-1", {"section": "summary"})
        assert result == "error: 'value' is required"

    async def test_unreachable_backend_returns_readable_message(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Name or service not known", request=request)

        client = _client_with_handler(handler)
        tool = update_profile_section_tool(client)
        result = await tool.handler("user-1", {"section": "summary", "value": "hi"})
        assert "temporarily unreachable" in result
        assert "Name or service not known" not in result


@pytest.mark.asyncio
class TestAddProfileItemTool:
    async def test_success_returns_confirmation(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"experience": []})

        client = _client_with_handler(handler)
        tool = add_profile_item_tool(client)
        result = await tool.handler(
            "user-1", {"section": "experience", "item": {"company": "Acme"}}
        )
        assert seen["body"] == {
            "user_id": "user-1",
            "section": "experience",
            "item": {"company": "Acme"},
        }
        assert result == "Added item to 'experience'."

    async def test_no_profile_returns_friendly_message(self):
        client = _client_with_handler(lambda r: httpx.Response(404, json={"detail": "x"}))
        tool = add_profile_item_tool(client)
        result = await tool.handler("user-1", {"section": "skills", "item": {}})
        assert "hasn't uploaded a resume" in result

    async def test_validation_error_returns_error_string(self):
        client = _client_with_handler(lambda r: httpx.Response(422, json={"detail": "bad item"}))
        tool = add_profile_item_tool(client)
        result = await tool.handler("user-1", {"section": "skills", "item": {}})
        assert result == "error: bad item"

    async def test_missing_item_returns_error_without_http_call(self):
        client = _client_with_handler(lambda r: httpx.Response(500))
        tool = add_profile_item_tool(client)
        result = await tool.handler("user-1", {"section": "skills"})
        assert result == "error: 'item' is required and must be an object"


@pytest.mark.asyncio
class TestRecordClarificationTool:
    async def test_success_calls_add_item_with_enrichment_section(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"enrichment": []})

        client = _client_with_handler(handler)
        tool = record_clarification_tool(client)
        result = await tool.handler("user-1", {"key": "team_size", "value": "6 engineers"})

        assert seen["url"] == "http://backend:8000/internal/profile/add-item"
        assert seen["body"] == {
            "user_id": "user-1",
            "section": "enrichment",
            "item": {"key": "team_size", "value": "6 engineers"},
        }
        assert result == "Recorded clarification: team_size = 6 engineers"

    async def test_missing_key_returns_error_without_http_call(self):
        client = _client_with_handler(lambda r: httpx.Response(500))
        tool = record_clarification_tool(client)
        result = await tool.handler("user-1", {"value": "6 engineers"})
        assert "required" in result

    async def test_no_profile_returns_friendly_message(self):
        client = _client_with_handler(lambda r: httpx.Response(404, json={"detail": "x"}))
        tool = record_clarification_tool(client)
        result = await tool.handler("user-1", {"key": "k", "value": "v"})
        assert "hasn't uploaded a resume" in result


@pytest.mark.asyncio
class TestDraftCvTool:
    async def test_success_returns_version_confirmation(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"document_id": "doc-1", "version": 3})

        client = _client_with_handler(handler)
        tool = draft_cv_tool(client)
        result = await tool.handler(
            "user-1", {"job_id": "job-1", "instructions": "focus on Go"}
        )

        assert seen["url"] == "http://backend:8000/internal/documents/draft-cv"
        assert seen["body"] == {
            "user_id": "user-1",
            "job_id": "job-1",
            "instructions": "focus on Go",
        }
        assert "Draft CV v3 created" in result

    async def test_missing_job_id_returns_error_without_http_call(self):
        client = _client_with_handler(lambda r: httpx.Response(500))
        tool = draft_cv_tool(client)
        result = await tool.handler("user-1", {})
        assert result == "error: 'job_id' is required"

    async def test_job_not_found_returns_friendly_message(self):
        client = _client_with_handler(lambda r: httpx.Response(404, json={"detail": "Job not found"}))
        tool = draft_cv_tool(client)
        result = await tool.handler("user-1", {"job_id": "no-such-job"})
        assert result == "That job could not be found."

    async def test_no_profile_returns_friendly_message(self):
        client = _client_with_handler(
            lambda r: httpx.Response(404, json={"detail": "No profile found yet — the user hasn't uploaded a resume."})
        )
        tool = draft_cv_tool(client)
        result = await tool.handler("user-1", {"job_id": "job-1"})
        assert "hasn't uploaded a resume" in result

    async def test_validation_error_returns_error_string(self):
        client = _client_with_handler(lambda r: httpx.Response(422, json={"detail": "bad instructions"}))
        tool = draft_cv_tool(client)
        result = await tool.handler("user-1", {"job_id": "job-1"})
        assert result == "error: bad instructions"

    async def test_unreachable_backend_returns_readable_message(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Name or service not known", request=request)

        client = _client_with_handler(handler)
        tool = draft_cv_tool(client)
        result = await tool.handler("user-1", {"job_id": "job-1"})
        assert "temporarily unreachable" in result


@pytest.mark.asyncio
class TestDraftCoverLetterTool:
    async def test_success_returns_version_confirmation(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"document_id": "doc-1", "version": 2})

        client = _client_with_handler(handler)
        tool = draft_cover_letter_tool(client)
        result = await tool.handler(
            "user-1", {"job_id": "job-1", "instructions": "mention my OSS work"}
        )

        assert seen["url"] == "http://backend:8000/internal/documents/draft-cover-letter"
        assert seen["body"] == {
            "user_id": "user-1",
            "job_id": "job-1",
            "instructions": "mention my OSS work",
        }
        assert "Draft cover letter v2 created" in result

    async def test_missing_job_id_returns_error_without_http_call(self):
        client = _client_with_handler(lambda r: httpx.Response(500))
        tool = draft_cover_letter_tool(client)
        result = await tool.handler("user-1", {})
        assert result == "error: 'job_id' is required"

    async def test_job_not_found_returns_friendly_message(self):
        client = _client_with_handler(lambda r: httpx.Response(404, json={"detail": "Job not found"}))
        tool = draft_cover_letter_tool(client)
        result = await tool.handler("user-1", {"job_id": "no-such-job"})
        assert result == "That job could not be found."

    async def test_no_profile_returns_friendly_message(self):
        client = _client_with_handler(
            lambda r: httpx.Response(404, json={"detail": "No profile found yet — the user hasn't uploaded a resume."})
        )
        tool = draft_cover_letter_tool(client)
        result = await tool.handler("user-1", {"job_id": "job-1"})
        assert "hasn't uploaded a resume" in result

    async def test_validation_error_returns_error_string(self):
        client = _client_with_handler(lambda r: httpx.Response(422, json={"detail": "bad instructions"}))
        tool = draft_cover_letter_tool(client)
        result = await tool.handler("user-1", {"job_id": "job-1"})
        assert result == "error: bad instructions"

    async def test_unreachable_backend_returns_readable_message(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Name or service not known", request=request)

        client = _client_with_handler(handler)
        tool = draft_cover_letter_tool(client)
        result = await tool.handler("user-1", {"job_id": "job-1"})
        assert "temporarily unreachable" in result


@pytest.mark.asyncio
class TestListApplicationStatusTool:
    async def test_success_returns_summary(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"summary": "Application for Engineer at Acme is at stage: Draft."})

        client = _client_with_handler(handler)
        tool = list_application_status_tool(client)
        result = await tool.handler("user-1", {"job_id": "job-1"})

        assert seen["url"] == "http://backend:8000/internal/applications/status"
        assert seen["body"] == {"user_id": "user-1", "job_id": "job-1"}
        assert result == "Application for Engineer at Acme is at stage: Draft."

    async def test_missing_job_id_returns_error_without_http_call(self):
        client = _client_with_handler(lambda r: httpx.Response(500))
        tool = list_application_status_tool(client)
        result = await tool.handler("user-1", {})
        assert result == "error: 'job_id' is required"

    async def test_job_not_found_returns_friendly_message(self):
        client = _client_with_handler(lambda r: httpx.Response(404, json={"detail": "Job not found"}))
        tool = list_application_status_tool(client)
        result = await tool.handler("user-1", {"job_id": "no-such-job"})
        assert result == "That job could not be found."

    async def test_unreachable_backend_returns_readable_message(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Name or service not known", request=request)

        client = _client_with_handler(handler)
        tool = list_application_status_tool(client)
        result = await tool.handler("user-1", {"job_id": "job-1"})
        assert "temporarily unreachable" in result


@pytest.mark.asyncio
class TestChangeApplicationStatusTool:
    async def test_success_returns_confirmation(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"stage": "Applied", "summary": "Application for Engineer at Acme is at stage: Applied."})

        client = _client_with_handler(handler)
        tool = change_application_status_tool(client)
        result = await tool.handler("user-1", {"job_id": "job-1", "stage": "Applied"})

        assert seen["url"] == "http://backend:8000/internal/applications/set-stage"
        assert seen["body"] == {"user_id": "user-1", "job_id": "job-1", "stage": "Applied"}
        assert "Application stage updated" in result
        assert "Applied" in result

    async def test_missing_job_id_returns_error_without_http_call(self):
        client = _client_with_handler(lambda r: httpx.Response(500))
        tool = change_application_status_tool(client)
        result = await tool.handler("user-1", {"stage": "Applied"})
        assert result == "error: 'job_id' is required"

    async def test_missing_stage_returns_error_without_http_call(self):
        client = _client_with_handler(lambda r: httpx.Response(500))
        tool = change_application_status_tool(client)
        result = await tool.handler("user-1", {"job_id": "job-1"})
        assert result == "error: 'stage' is required"

    async def test_job_not_found_returns_friendly_message(self):
        client = _client_with_handler(lambda r: httpx.Response(404, json={"detail": "Job not found"}))
        tool = change_application_status_tool(client)
        result = await tool.handler("user-1", {"job_id": "no-such-job", "stage": "Applied"})
        assert result == "That job could not be found."

    async def test_invalid_stage_returns_error_string(self):
        client = _client_with_handler(
            lambda r: httpx.Response(422, json={"detail": "Invalid stage — valid stages are: Draft, Applied"})
        )
        tool = change_application_status_tool(client)
        result = await tool.handler("user-1", {"job_id": "job-1", "stage": "Nonsense"})
        assert result == "error: Invalid stage — valid stages are: Draft, Applied"

    async def test_unreachable_backend_returns_readable_message(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Name or service not known", request=request)

        client = _client_with_handler(handler)
        tool = change_application_status_tool(client)
        result = await tool.handler("user-1", {"job_id": "job-1", "stage": "Applied"})
        assert "temporarily unreachable" in result


@pytest.mark.asyncio
class TestSystemPromptFn:
    async def test_success_returns_context(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"context": "profile info here"})

        client = _client_with_handler(handler)
        fn = build_system_prompt_fn(client)
        result = await fn("user-1", "user-1:profile")

        assert seen["body"] == {"user_id": "user-1", "conversation_id": "user-1:profile"}
        assert result == "profile info here"

    async def test_backend_error_returns_empty_string(self):
        client = _client_with_handler(lambda r: httpx.Response(500))
        fn = build_system_prompt_fn(client)
        result = await fn("user-1", "user-1:profile")
        assert result == ""

    async def test_network_error_returns_empty_string(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        client = _client_with_handler(handler)
        fn = build_system_prompt_fn(client)
        result = await fn("user-1", "user-1:profile")
        assert result == ""
