"""M4 internal API tests — secret enforcement, context building, section writes, isolation."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import Document, Job, Profile
from app.llm.deps import get_llm
from app.llm.schemas import ProfileModel, TailoredCV
from app.main import app

_SECRET = "test-internal-secret"


@pytest.fixture(autouse=True)
def _internal_secret(monkeypatch):
    monkeypatch.setenv("AGENT_INTERNAL_SECRET", _SECRET)


def _headers(secret: str | None = _SECRET) -> dict:
    return {"X-Internal-Secret": secret} if secret is not None else {}


def _signup(client, email: str, password: str = "password123") -> dict:
    r = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


def _seed_profile(db_session, user_id: str) -> Profile:
    data = ProfileModel(summary="Experienced engineer.").model_dump()
    profile = Profile(user_id=user_id, version=1, data=data)
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


def _seed_job(db_session, user_id: str) -> Job:
    job = Job(
        user_id=user_id,
        source_url="https://example.com/job",
        raw_text="raw text",
        parsed={"company": "Acme", "title": "Engineer", "location": "Remote", "seniority": "mid"},
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


class TestSecretEnforcement:
    def test_missing_secret_rejected(self, client):
        r = client.post("/internal/context", json={"user_id": "u", "conversation_id": "profile"})
        assert r.status_code == 403

    def test_wrong_secret_rejected(self, client):
        r = client.post(
            "/internal/context",
            json={"user_id": "u", "conversation_id": "profile"},
            headers=_headers("wrong-secret"),
        )
        assert r.status_code == 403

    def test_profile_endpoints_reject_missing_secret(self, client):
        r = client.post(
            "/internal/profile/update-section",
            json={"user_id": "u", "section": "summary", "value": "x"},
        )
        assert r.status_code == 403

        r2 = client.post(
            "/internal/profile/add-item",
            json={"user_id": "u", "section": "skills", "item": {}},
        )
        assert r2.status_code == 403


class TestContext:
    def test_no_profile_returns_build_from_scratch_message(self, client):
        user = _signup(client, "a@example.com")
        r = client.post(
            "/internal/context",
            json={"user_id": user["id"], "conversation_id": "profile"},
            headers=_headers(),
        )
        assert r.status_code == 200
        assert "has not uploaded a resume" in r.json()["context"]

    def test_profile_mode_includes_profile_data(self, client, db_session):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])

        r = client.post(
            "/internal/context",
            json={"user_id": user["id"], "conversation_id": "profile"},
            headers=_headers(),
        )
        assert r.status_code == 200
        assert "Experienced engineer." in r.json()["context"]

    def test_generation_suffix_is_stripped(self, client, db_session):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])

        r = client.post(
            "/internal/context",
            json={"user_id": user["id"], "conversation_id": "profile.3"},
            headers=_headers(),
        )
        assert r.status_code == 200
        assert "Experienced engineer." in r.json()["context"]

    def test_namespaced_conversation_id_is_stripped(self, client, db_session):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])

        r = client.post(
            "/internal/context",
            json={"user_id": user["id"], "conversation_id": f"{user['id']}:profile"},
            headers=_headers(),
        )
        assert r.status_code == 200
        assert "Experienced engineer." in r.json()["context"]

    def test_job_mode_includes_profile_and_job(self, client, db_session):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])
        job = _seed_job(db_session, user["id"])

        r = client.post(
            "/internal/context",
            json={"user_id": user["id"], "conversation_id": f"job:{job.id}"},
            headers=_headers(),
        )
        assert r.status_code == 200
        context = r.json()["context"]
        assert "Experienced engineer." in context
        assert "Acme" in context

    def test_job_mode_foreign_job_id_returns_not_found_block(self, client, db_session):
        user_a = _signup(client, "a@example.com")
        job = _seed_job(db_session, user_a["id"])

        user_b = _signup(client, "b@example.com")
        r = client.post(
            "/internal/context",
            json={"user_id": user_b["id"], "conversation_id": f"job:{job.id}"},
            headers=_headers(),
        )
        assert r.status_code == 200
        context = r.json()["context"]
        assert "could not be found" in context
        assert "Acme" not in context


class TestUpdateSection:
    def test_update_summary_persists_and_bumps_version(self, client, db_session):
        user = _signup(client, "a@example.com")
        profile = _seed_profile(db_session, user["id"])

        r = client.post(
            "/internal/profile/update-section",
            json={"user_id": user["id"], "section": "summary", "value": "New summary"},
            headers=_headers(),
        )
        assert r.status_code == 200
        assert r.json()["summary"] == "New summary"

        db_session.refresh(profile)
        assert profile.data["summary"] == "New summary"
        assert profile.version == 2

    def test_update_experience_validates_list_shape(self, client, db_session):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])

        r = client.post(
            "/internal/profile/update-section",
            json={"user_id": user["id"], "section": "experience", "value": "not a list"},
            headers=_headers(),
        )
        assert r.status_code == 422

    def test_unknown_section_rejected(self, client, db_session):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])

        r = client.post(
            "/internal/profile/update-section",
            json={"user_id": user["id"], "section": "bogus", "value": "x"},
            headers=_headers(),
        )
        assert r.status_code == 422

    def test_no_profile_returns_404(self, client):
        r = client.post(
            "/internal/profile/update-section",
            json={"user_id": "no-such-user", "section": "summary", "value": "x"},
            headers=_headers(),
        )
        assert r.status_code == 404


class TestAddItem:
    def test_add_experience_item_appends_without_clobbering(self, client, db_session):
        user = _signup(client, "a@example.com")
        profile = _seed_profile(db_session, user["id"])
        profile.data = {**profile.data, "experience": [{"company": "Old Co", "position": "Dev"}]}
        db_session.commit()

        r = client.post(
            "/internal/profile/add-item",
            json={
                "user_id": user["id"],
                "section": "experience",
                "item": {"company": "New Co", "position": "Senior Dev"},
            },
            headers=_headers(),
        )
        assert r.status_code == 200
        experience = r.json()["experience"]
        assert len(experience) == 2
        assert experience[0]["company"] == "Old Co"
        assert experience[1]["company"] == "New Co"

    def test_add_enrichment_item_record_clarification_path(self, client, db_session):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])

        r = client.post(
            "/internal/profile/add-item",
            json={
                "user_id": user["id"],
                "section": "enrichment",
                "item": {"key": "team_size", "value": "6 engineers"},
            },
            headers=_headers(),
        )
        assert r.status_code == 200
        enrichment = r.json()["enrichment"]
        assert enrichment == [{"key": "team_size", "value": "6 engineers"}]

    def test_add_item_to_non_list_section_rejected(self, client, db_session):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])

        r = client.post(
            "/internal/profile/add-item",
            json={"user_id": user["id"], "section": "summary", "item": {}},
            headers=_headers(),
        )
        assert r.status_code == 422


def _fake_tailored_cv() -> TailoredCV:
    return TailoredCV(
        summary="Tailored.",
        section_order=["experience"],
        skills=[],
        experience=[],
        projects=[],
        education=[],
        publications=[],
        extras=[],
    )


@pytest.fixture()
def patched_llm_client(client):
    fake_response = MagicMock()
    fake_response.parsed = _fake_tailored_cv()
    fake_llm = MagicMock()
    fake_llm.invoke = AsyncMock(return_value=fake_response)
    app.dependency_overrides[get_llm] = lambda: fake_llm
    yield client, fake_llm
    app.dependency_overrides.pop(get_llm, None)


class TestDraftCv:
    def test_creates_document_v1(self, patched_llm_client, db_session):
        client, _ = patched_llm_client
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])
        job = _seed_job(db_session, user["id"])

        r = client.post(
            "/internal/documents/draft-cv",
            json={"user_id": user["id"], "job_id": job.id},
            headers=_headers(),
        )
        assert r.status_code == 200, r.text
        assert r.json()["version"] == 1

        doc = db_session.query(Document).filter_by(id=r.json()["document_id"]).first()
        assert doc.user_id == user["id"]
        assert doc.job_id == job.id
        assert doc.type == "cv"
        assert "cv:" in doc.source_text

    def test_second_draft_bumps_version(self, patched_llm_client, db_session):
        client, _ = patched_llm_client
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])
        job = _seed_job(db_session, user["id"])

        client.post(
            "/internal/documents/draft-cv",
            json={"user_id": user["id"], "job_id": job.id},
            headers=_headers(),
        )
        r = client.post(
            "/internal/documents/draft-cv",
            json={"user_id": user["id"], "job_id": job.id},
            headers=_headers(),
        )
        assert r.json()["version"] == 2

    def test_missing_job_returns_404(self, patched_llm_client, db_session):
        client, _ = patched_llm_client
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])

        r = client.post(
            "/internal/documents/draft-cv",
            json={"user_id": user["id"], "job_id": "no-such-job"},
            headers=_headers(),
        )
        assert r.status_code == 404

    def test_missing_profile_returns_404(self, patched_llm_client, db_session):
        client, _ = patched_llm_client
        user = _signup(client, "a@example.com")
        job = _seed_job(db_session, user["id"])

        r = client.post(
            "/internal/documents/draft-cv",
            json={"user_id": user["id"], "job_id": job.id},
            headers=_headers(),
        )
        assert r.status_code == 404

    def test_missing_secret_rejected(self, client):
        r = client.post(
            "/internal/documents/draft-cv", json={"user_id": "u", "job_id": "j"}
        )
        assert r.status_code == 403


class TestDraftCvIsolation:
    def test_user_b_cannot_draft_cv_for_user_a_job(self, patched_llm_client, db_session):
        client, _ = patched_llm_client
        user_a = _signup(client, "a@example.com")
        _seed_profile(db_session, user_a["id"])
        job = _seed_job(db_session, user_a["id"])

        user_b = _signup(client, "b@example.com")
        _seed_profile(db_session, user_b["id"])

        r = client.post(
            "/internal/documents/draft-cv",
            json={"user_id": user_b["id"], "job_id": job.id},
            headers=_headers(),
        )
        assert r.status_code == 404


class TestIsolation:
    def test_user_b_cannot_update_user_a_profile(self, client, db_session):
        user_a = _signup(client, "a@example.com")
        _seed_profile(db_session, user_a["id"])
        user_b = _signup(client, "b@example.com")

        r = client.post(
            "/internal/profile/update-section",
            json={"user_id": user_b["id"], "section": "summary", "value": "hijacked"},
            headers=_headers(),
        )
        assert r.status_code == 404

    def test_user_b_cannot_add_item_to_user_a_profile(self, client, db_session):
        user_a = _signup(client, "a@example.com")
        _seed_profile(db_session, user_a["id"])
        user_b = _signup(client, "b@example.com")

        r = client.post(
            "/internal/profile/add-item",
            json={"user_id": user_b["id"], "section": "skills", "item": {"label": "x", "details": "y"}},
            headers=_headers(),
        )
        assert r.status_code == 404
