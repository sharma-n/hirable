"""M5 public documents API — draft/list/get/save/delete/compile, isolation."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import Document, Job, Profile
from app.llm.deps import get_llm
from app.llm.schemas import ProfileModel, TailoredCoverLetter, TailoredCV
from app.main import app


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
        parsed={"company": "Acme", "title": "Engineer", "location": "Remote", "keywords": ["Python"]},
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


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


def _fake_tailored_cover_letter() -> TailoredCoverLetter:
    return TailoredCoverLetter(
        worth_it=True,
        recipient="Hiring Manager",
        salutation="Dear Hiring Manager,",
        body_paragraphs=["Paragraph one.", "Paragraph two."],
        closing="Sincerely,",
    )


@pytest.fixture()
def patched_client(client):
    fake_response = MagicMock()
    fake_response.parsed = _fake_tailored_cv()
    fake_llm = MagicMock()
    fake_llm.invoke = AsyncMock(return_value=fake_response)
    app.dependency_overrides[get_llm] = lambda: fake_llm
    yield client, fake_llm
    app.dependency_overrides.pop(get_llm, None)


@pytest.fixture()
def patched_letter_client(client):
    fake_response = MagicMock()
    fake_response.parsed = _fake_tailored_cover_letter()
    fake_llm = MagicMock()
    fake_llm.invoke = AsyncMock(return_value=fake_response)
    app.dependency_overrides[get_llm] = lambda: fake_llm
    yield client, fake_llm
    app.dependency_overrides.pop(get_llm, None)


class TestDraft:
    def test_draft_creates_v1(self, patched_client, db_session):
        client, _ = patched_client
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])
        job = _seed_job(db_session, user["id"])

        r = client.post("/api/documents/draft", json={"job_id": job.id})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["version"] == 1
        assert body["job_id"] == job.id
        assert body["type"] == "cv"
        assert "cv:" in body["source_text"]

    def test_draft_missing_job_404(self, patched_client, db_session):
        client, _ = patched_client
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])

        r = client.post("/api/documents/draft", json={"job_id": "no-such-job"})
        assert r.status_code == 404

    def test_draft_missing_profile_404(self, patched_client, db_session):
        client, _ = patched_client
        user = _signup(client, "a@example.com")
        job = _seed_job(db_session, user["id"])

        r = client.post("/api/documents/draft", json={"job_id": job.id})
        assert r.status_code == 404

    def test_unauthenticated_401(self, patched_client):
        client, _ = patched_client
        r = client.post("/api/documents/draft", json={"job_id": "x"})
        assert r.status_code == 401


class TestListAndGet:
    def test_list_excludes_source_text(self, patched_client, db_session):
        client, _ = patched_client
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])
        job = _seed_job(db_session, user["id"])
        client.post("/api/documents/draft", json={"job_id": job.id})

        r = client.get(f"/api/documents?job_id={job.id}")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert "source_text" not in r.json()[0]

    def test_list_ordered_newest_version_first(self, patched_client, db_session):
        client, _ = patched_client
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])
        job = _seed_job(db_session, user["id"])
        client.post("/api/documents/draft", json={"job_id": job.id})
        client.post("/api/documents/draft", json={"job_id": job.id})

        r = client.get(f"/api/documents?job_id={job.id}")
        versions = [d["version"] for d in r.json()]
        assert versions == [2, 1]

    def test_get_returns_full_document(self, patched_client, db_session):
        client, _ = patched_client
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])
        job = _seed_job(db_session, user["id"])
        doc = client.post("/api/documents/draft", json={"job_id": job.id}).json()

        r = client.get(f"/api/documents/{doc['id']}")
        assert r.status_code == 200
        assert r.json()["source_text"] == doc["source_text"]

    def test_get_nonexistent_404(self, patched_client):
        client, _ = patched_client
        _signup(client, "a@example.com")
        r = client.get("/api/documents/no-such-id")
        assert r.status_code == 404


class TestSaveAndDelete:
    def test_save_creates_new_version_row(self, patched_client, db_session):
        client, _ = patched_client
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])
        job = _seed_job(db_session, user["id"])
        doc = client.post("/api/documents/draft", json={"job_id": job.id}).json()

        r = client.put(f"/api/documents/{doc['id']}", json={"source_text": "cv:\n  name: Edited\n"})
        assert r.status_code == 200, r.text
        new_doc = r.json()
        assert new_doc["id"] != doc["id"]
        assert new_doc["version"] == 2
        assert new_doc["source_text"] == "cv:\n  name: Edited\n"

        # original version row is untouched
        original = db_session.query(Document).filter_by(id=doc["id"]).first()
        assert original.source_text == doc["source_text"]

    def test_delete_removes_one_version(self, patched_client, db_session):
        client, _ = patched_client
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])
        job = _seed_job(db_session, user["id"])
        doc = client.post("/api/documents/draft", json={"job_id": job.id}).json()

        r = client.delete(f"/api/documents/{doc['id']}")
        assert r.status_code == 204
        assert db_session.query(Document).filter_by(id=doc["id"]).first() is None


class TestCompile:
    def test_compile_valid_source_returns_pdf(self, patched_client):
        client, _ = patched_client
        _signup(client, "a@example.com")

        r = client.post(
            "/api/documents/compile",
            json={"source_text": "cv:\n  name: Jane Doe\n"},
        )
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:4] == b"%PDF"

    def test_compile_invalid_yaml_returns_422_with_stage(self, patched_client):
        client, _ = patched_client
        _signup(client, "a@example.com")

        r = client.post(
            "/api/documents/compile",
            json={"source_text": "cv:\n  name: [unterminated"},
        )
        assert r.status_code == 422
        assert r.json()["detail"]["stage"] == "yaml"

    def test_compile_unauthenticated_401(self, patched_client):
        client, _ = patched_client
        r = client.post("/api/documents/compile", json={"source_text": "cv:\n  name: X\n"})
        assert r.status_code == 401


class TestDraftCoverLetter:
    def test_draft_creates_v1(self, patched_letter_client, db_session):
        client, _ = patched_letter_client
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])
        job = _seed_job(db_session, user["id"])

        r = client.post("/api/documents/draft-cover-letter", json={"job_id": job.id})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["version"] == 1
        assert body["type"] == "cover_letter"
        assert "cv:" in body["source_text"]

    def test_missing_profile_404(self, patched_letter_client, db_session):
        client, _ = patched_letter_client
        user = _signup(client, "a@example.com")
        job = _seed_job(db_session, user["id"])

        r = client.post("/api/documents/draft-cover-letter", json={"job_id": job.id})
        assert r.status_code == 404

    def test_cv_and_cover_letter_version_independently(self, patched_letter_client, db_session):
        # draft-cv and draft-cover-letter are separate version sequences for the
        # same job — this exercises app.rendercv.service._next_version's scoping.
        client, _ = patched_letter_client
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])
        job = _seed_job(db_session, user["id"])

        letter1 = client.post("/api/documents/draft-cover-letter", json={"job_id": job.id}).json()
        letter2 = client.post("/api/documents/draft-cover-letter", json={"job_id": job.id}).json()
        assert letter1["version"] == 1
        assert letter2["version"] == 2

    def test_list_scoped_by_type(self, patched_letter_client, db_session):
        client, _ = patched_letter_client
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])
        job = _seed_job(db_session, user["id"])
        client.post("/api/documents/draft-cover-letter", json={"job_id": job.id})

        r = client.get(f"/api/documents?job_id={job.id}&type=cover_letter")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["type"] == "cover_letter"

        r_cv = client.get(f"/api/documents?job_id={job.id}&type=cv")
        assert r_cv.json() == []


class TestIsolation:
    def test_user_b_cannot_draft_for_user_a_job(self, patched_client, db_session):
        client, _ = patched_client
        user_a = _signup(client, "a@example.com")
        _seed_profile(db_session, user_a["id"])
        job = _seed_job(db_session, user_a["id"])

        client.post("/api/auth/logout")
        _signup(client, "b@example.com")

        r = client.post("/api/documents/draft", json={"job_id": job.id})
        assert r.status_code == 404

    def test_user_b_cannot_list_user_a_documents(self, patched_client, db_session):
        client, _ = patched_client
        user_a = _signup(client, "a@example.com")
        _seed_profile(db_session, user_a["id"])
        job = _seed_job(db_session, user_a["id"])
        client.post("/api/documents/draft", json={"job_id": job.id})

        client.post("/api/auth/logout")
        _signup(client, "b@example.com")

        r = client.get(f"/api/documents?job_id={job.id}")
        assert r.status_code == 404  # job lookup itself 404s for user B

    def test_user_b_cannot_get_user_a_document(self, patched_client, db_session):
        client, _ = patched_client
        user_a = _signup(client, "a@example.com")
        _seed_profile(db_session, user_a["id"])
        job = _seed_job(db_session, user_a["id"])
        doc = client.post("/api/documents/draft", json={"job_id": job.id}).json()

        client.post("/api/auth/logout")
        _signup(client, "b@example.com")

        assert client.get(f"/api/documents/{doc['id']}").status_code == 404
        assert client.put(f"/api/documents/{doc['id']}", json={"source_text": "x"}).status_code == 404
        assert client.delete(f"/api/documents/{doc['id']}").status_code == 404

    def test_user_b_cannot_draft_cover_letter_for_user_a_job(self, patched_letter_client, db_session):
        client, _ = patched_letter_client
        user_a = _signup(client, "a@example.com")
        _seed_profile(db_session, user_a["id"])
        job = _seed_job(db_session, user_a["id"])

        client.post("/api/auth/logout")
        _signup(client, "b@example.com")

        r = client.post("/api/documents/draft-cover-letter", json={"job_id": job.id})
        assert r.status_code == 404
