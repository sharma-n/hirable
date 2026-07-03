"""M3 job ingest acceptance tests — add by URL, paste fallback, CRUD, isolation."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm.deps import get_llm
from app.llm.schemas import JobModel
from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CANNED_JOB = JobModel(
    company="Acme Corp",
    title="Senior Backend Engineer",
    location="Remote",
    responsibilities=["Design APIs", "Mentor engineers"],
    must_have=["Python", "5+ years experience"],
    nice_to_have=["Kubernetes"],
    keywords=["FastAPI", "PostgreSQL"],
    why_opened_guess="Team growth",
    seniority="senior",
    company_type="startup",
    team_name="Payments Platform",
    team_description="Owns checkout and billing infrastructure",
)


def _make_fake_llm() -> MagicMock:
    """Return a mock LLMClient whose invoke returns _CANNED_JOB."""
    fake_response = MagicMock()
    fake_response.parsed = _CANNED_JOB
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def patched_client(client):
    """client fixture with get_llm + fetch_job_text overridden.

    fetch_job_text defaults to returning fetchable text; individual tests
    override .return_value to simulate a blocked/empty fetch.
    """
    fake_llm = _make_fake_llm()
    app.dependency_overrides[get_llm] = lambda: fake_llm
    with patch("app.api.jobs.fetch_job_text") as fake_fetch:
        fake_fetch.return_value = "Full job posting text about a senior backend role…"
        yield client, fake_llm, fake_fetch
    app.dependency_overrides.pop(get_llm, None)


class TestAddJobByUrl:
    def test_url_fetch_success_creates_job(self, patched_client):
        client, fake_llm, fake_fetch = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")

        r = client.post("/api/jobs", json={"url": "https://example.com/job"})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["needs_paste"] is False
        assert body["job"]["parsed"]["company"] == "Acme Corp"
        assert body["job"]["source_url"] == "https://example.com/job"
        # JobModel is flat — a single llm.invoke() call is expected (unlike
        # ProfileModel's Part1/Part2 split for its nested list-of-object fields).
        assert fake_llm.invoke.call_count == 1
        fake_fetch.assert_called_once_with("https://example.com/job")

    def test_unauthenticated_rejected(self, client):
        r = client.post("/api/jobs", json={"url": "https://example.com/job"})
        assert r.status_code == 401


class TestAddJobNeedsPaste:
    def test_blocked_fetch_returns_needs_paste(self, patched_client):
        client, fake_llm, fake_fetch = patched_client
        fake_fetch.return_value = None
        _signup(client, "u@example.com")
        _login(client, "u@example.com")

        r = client.post("/api/jobs", json={"url": "https://blocked.example.com/job"})
        assert r.status_code == 200
        assert r.json() == {"needs_paste": True, "job": None}
        fake_llm.invoke.assert_not_called()


class TestAddJobByPasteFallback:
    def test_raw_text_bypasses_fetch_even_with_url(self, patched_client):
        client, fake_llm, fake_fetch = patched_client
        fake_fetch.return_value = None
        _signup(client, "u@example.com")
        _login(client, "u@example.com")

        r1 = client.post("/api/jobs", json={"url": "https://blocked.example.com/job"})
        assert r1.json()["needs_paste"] is True

        fake_fetch.reset_mock()
        r2 = client.post(
            "/api/jobs",
            json={"url": "https://blocked.example.com/job", "raw_text": "pasted job text"},
        )
        assert r2.status_code == 201, r2.text
        body = r2.json()
        assert body["needs_paste"] is False
        assert body["job"]["source_url"] == "https://blocked.example.com/job"
        assert body["job"]["raw_text"] == "pasted job text"
        fake_fetch.assert_not_called()


class TestAddJobByPasteOnly:
    def test_raw_text_only_no_url(self, patched_client):
        client, fake_llm, fake_fetch = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")

        r = client.post("/api/jobs", json={"raw_text": "pasted job text only"})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["job"]["source_url"] is None
        assert body["job"]["raw_text"] == "pasted job text only"
        fake_fetch.assert_not_called()


class TestAddJobValidation:
    def test_empty_body_rejected(self, patched_client):
        client, _, _ = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")
        r = client.post("/api/jobs", json={})
        assert r.status_code == 422


class TestListJobs:
    def test_empty_for_fresh_user(self, patched_client):
        client, _, _ = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")
        r = client.get("/api/jobs")
        assert r.status_code == 200
        assert r.json() == []

    def test_lists_newest_first(self, patched_client):
        client, _, _ = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")
        client.post("/api/jobs", json={"url": "https://example.com/job1"})
        client.post("/api/jobs", json={"url": "https://example.com/job2"})

        r = client.get("/api/jobs")
        assert r.status_code == 200
        jobs = r.json()
        assert len(jobs) == 2
        assert jobs[0]["source_url"] == "https://example.com/job2"

    def test_unauthenticated_rejected(self, client):
        r = client.get("/api/jobs")
        assert r.status_code == 401


class TestGetJob:
    def test_get_own_job(self, patched_client):
        client, _, _ = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")
        created = client.post("/api/jobs", json={"url": "https://example.com/job"}).json()

        r = client.get(f"/api/jobs/{created['job']['id']}")
        assert r.status_code == 200
        assert r.json()["parsed"]["company"] == "Acme Corp"

    def test_nonexistent_returns_404(self, patched_client):
        client, _, _ = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")
        r = client.get("/api/jobs/does-not-exist")
        assert r.status_code == 404


class TestUpdateJob:
    def test_put_persists_edits_and_bumps_updated_at(self, patched_client):
        client, _, _ = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")
        created = client.post("/api/jobs", json={"url": "https://example.com/job"}).json()
        job = created["job"]

        edited = dict(_CANNED_JOB.model_dump())
        edited["title"] = "Staff Backend Engineer"

        r = client.put(f"/api/jobs/{job['id']}", json=edited)
        assert r.status_code == 200
        body = r.json()
        assert body["parsed"]["title"] == "Staff Backend Engineer"
        assert body["updated_at"] != job["updated_at"] or body["updated_at"] >= job["updated_at"]

    def test_put_nonexistent_returns_404(self, patched_client):
        client, _, _ = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")
        r = client.put("/api/jobs/does-not-exist", json=_CANNED_JOB.model_dump())
        assert r.status_code == 404

    def test_unauthenticated_rejected(self, client):
        r = client.put("/api/jobs/some-id", json=_CANNED_JOB.model_dump())
        assert r.status_code == 401


class TestDeleteJob:
    def test_delete_then_get_404(self, patched_client):
        client, _, _ = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")
        created = client.post("/api/jobs", json={"url": "https://example.com/job"}).json()
        job_id = created["job"]["id"]

        r = client.delete(f"/api/jobs/{job_id}")
        assert r.status_code == 204

        r2 = client.get(f"/api/jobs/{job_id}")
        assert r2.status_code == 404

    def test_delete_nonexistent_returns_404(self, patched_client):
        client, _, _ = patched_client
        _signup(client, "u@example.com")
        _login(client, "u@example.com")
        r = client.delete("/api/jobs/does-not-exist")
        assert r.status_code == 404


class TestIsolation:
    def test_user_b_list_excludes_user_a_jobs(self, patched_client):
        client, _, _ = patched_client
        _signup(client, "a@example.com")
        _login(client, "a@example.com")
        client.post("/api/jobs", json={"url": "https://example.com/job"})

        _signup(client, "b@example.com")
        _login(client, "b@example.com")
        r = client.get("/api/jobs")
        assert r.json() == []

    def test_user_b_cannot_get_user_a_job(self, patched_client):
        client, _, _ = patched_client
        _signup(client, "a@example.com")
        _login(client, "a@example.com")
        created = client.post("/api/jobs", json={"url": "https://example.com/job"}).json()
        job_id = created["job"]["id"]

        _signup(client, "b@example.com")
        _login(client, "b@example.com")
        r = client.get(f"/api/jobs/{job_id}")
        assert r.status_code == 404

    def test_user_b_cannot_put_user_a_job(self, patched_client):
        client, _, _ = patched_client
        _signup(client, "a@example.com")
        _login(client, "a@example.com")
        created = client.post("/api/jobs", json={"url": "https://example.com/job"}).json()
        job_id = created["job"]["id"]

        _signup(client, "b@example.com")
        _login(client, "b@example.com")
        r = client.put(f"/api/jobs/{job_id}", json=_CANNED_JOB.model_dump())
        assert r.status_code == 404

    def test_user_b_cannot_delete_user_a_job(self, patched_client):
        client, _, _ = patched_client
        _signup(client, "a@example.com")
        _login(client, "a@example.com")
        created = client.post("/api/jobs", json={"url": "https://example.com/job"}).json()
        job_id = created["job"]["id"]

        _signup(client, "b@example.com")
        _login(client, "b@example.com")
        r = client.delete(f"/api/jobs/{job_id}")
        assert r.status_code == 404


class TestFetchJobText:
    """Unit-level tests of fetch_job_text() itself, mocking trafilatura directly."""

    def test_blocked_fetch_returns_none(self):
        from app.parsing.jobs import fetch_job_text

        with patch("app.parsing.jobs.trafilatura.fetch_url", return_value=None):
            assert fetch_job_text("https://example.com/job") is None

    def test_empty_extraction_returns_none(self):
        from app.parsing.jobs import fetch_job_text

        with patch("app.parsing.jobs.trafilatura.fetch_url", return_value="<html></html>"), \
             patch("app.parsing.jobs.trafilatura.extract", return_value=None):
            assert fetch_job_text("https://example.com/job") is None

    def test_happy_path_returns_text(self):
        from app.parsing.jobs import fetch_job_text

        with patch("app.parsing.jobs.trafilatura.fetch_url", return_value="<html>...</html>"), \
             patch("app.parsing.jobs.trafilatura.extract", return_value="Job posting text"):
            assert fetch_job_text("https://example.com/job") == "Job posting text"

    def test_unexpected_exception_returns_none(self):
        from app.parsing.jobs import fetch_job_text

        with patch("app.parsing.jobs.trafilatura.fetch_url", side_effect=RuntimeError("boom")):
            assert fetch_job_text("https://example.com/job") is None
