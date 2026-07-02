"""M2 profile acceptance tests — resume upload, editor CRUD, isolation."""
from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm.deps import get_llm
from app.llm.schemas import ContactInfo, ProfileModel, SkillItem
from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CANNED_PROFILE = ProfileModel(
    contact=ContactInfo(name="Jane Doe", email="jane@example.com"),
    summary="Software engineer",
    skills=[SkillItem(label="Languages", details="Python, FastAPI")],
)


def _make_fake_llm() -> MagicMock:
    """Return a mock LLMClient whose invoke returns _CANNED_PROFILE."""
    fake_response = MagicMock()
    fake_response.parsed = _CANNED_PROFILE
    fake_llm = MagicMock()
    fake_llm.invoke = AsyncMock(return_value=fake_response)
    return fake_llm


def _signup(client, email: str, password: str = "password123") -> dict:
    r = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


def _login(client, email: str, password: str = "password123") -> None:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text


def _upload_tex(client) -> dict:
    tex_content = b"\\section{Experience}\nSoftware Engineer at Acme 2020--2023"
    r = client.post(
        "/api/profile/resume",
        files={"file": ("resume.tex", io.BytesIO(tex_content), "application/octet-stream")},
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def patched_client(client):
    """client fixture with get_llm + save_upload overridden."""
    fake_llm = _make_fake_llm()
    app.dependency_overrides[get_llm] = lambda: fake_llm
    with patch("app.api.profile.save_upload"):
        yield client, fake_llm
    # dependency_overrides is cleared by the base client fixture on teardown
    app.dependency_overrides.pop(get_llm, None)


class TestGetProfileEmpty:
    def test_unauthenticated_returns_401(self, client):
        r = client.get("/api/profile")
        assert r.status_code == 401

    def test_no_profile_returns_204(self, patched_client):
        client, _ = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")
        r = client.get("/api/profile")
        assert r.status_code == 204


class TestUploadResume:
    def test_upload_creates_profile_v1(self, patched_client):
        client, fake_llm = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")

        data = _upload_tex(client)

        assert data["version"] == 1
        assert data["data"]["contact"]["name"] == "Jane Doe"
        # parse_resume splits extraction into two concurrent structured-output
        # calls (see app/parsing/profile.py) to stay under Anthropic's
        # compiled-grammar size limit.
        assert fake_llm.invoke.call_count == 2

    def test_get_returns_profile_after_upload(self, patched_client):
        client, _ = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")
        _upload_tex(client)

        r = client.get("/api/profile")
        assert r.status_code == 200
        assert r.json()["version"] == 1

    def test_unsupported_extension_rejected(self, patched_client):
        client, _ = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")
        r = client.post(
            "/api/profile/resume",
            files={"file": ("resume.txt", io.BytesIO(b"text"), "text/plain")},
        )
        assert r.status_code == 415

    def test_unauthenticated_upload_rejected(self, client):
        r = client.post(
            "/api/profile/resume",
            files={"file": ("resume.tex", io.BytesIO(b"hi"), "application/octet-stream")},
        )
        assert r.status_code == 401

    def test_reupload_overwrites_and_bumps_version(self, patched_client):
        client, _ = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")

        _upload_tex(client)
        data = _upload_tex(client)

        assert data["version"] == 2


class TestUpdateProfile:
    def test_put_edits_persist_and_bump_version(self, patched_client):
        client, _ = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")
        _upload_tex(client)

        updated_data = _CANNED_PROFILE.model_dump()
        updated_data["summary"] = "Senior engineer"

        r = client.put("/api/profile", json=updated_data)
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["summary"] == "Senior engineer"
        assert body["version"] == 2

    def test_put_without_profile_returns_404(self, patched_client):
        client, _ = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")
        r = client.put("/api/profile", json=_CANNED_PROFILE.model_dump())
        assert r.status_code == 404

    def test_unauthenticated_put_rejected(self, client):
        r = client.put("/api/profile", json=_CANNED_PROFILE.model_dump())
        assert r.status_code == 401


class TestIsolation:
    def test_user_b_cannot_get_user_a_profile(self, patched_client):
        client, _ = patched_client
        # Create and upload as user A
        _signup(client, "a@example.com")
        _login(client, "a@example.com")
        _upload_tex(client)

        # Switch to user B
        _signup(client, "b@example.com")
        _login(client, "b@example.com")
        r = client.get("/api/profile")
        assert r.status_code == 204  # B has no profile

    def test_user_b_cannot_put_user_a_profile(self, patched_client):
        client, _ = patched_client
        _signup(client, "a@example.com")
        _login(client, "a@example.com")
        _upload_tex(client)

        _signup(client, "b@example.com")
        _login(client, "b@example.com")
        r = client.put("/api/profile", json=_CANNED_PROFILE.model_dump())
        # B has no profile → 404 (cannot touch A's)
        assert r.status_code == 404


class TestTexExtraction:
    def test_strip_latex_produces_plain_text(self):
        from app.parsing.extract import _strip_latex

        tex = r"\section{Experience}\textbf{Engineer} at \textit{Acme}"
        result = _strip_latex(tex)
        assert "Experience" in result
        assert "Engineer" in result
        assert "Acme" in result
        assert "\\" not in result
