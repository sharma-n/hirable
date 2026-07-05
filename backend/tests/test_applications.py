"""M7 application tracking + automation — auto-create/backfill, stage
transitions, submit snapshotting, automation time-travel, isolation, cascade.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.applications.automation import apply_automation
from app.applications.service import backfill_applications, get_or_create_application, transition_stage
from app.db.models import Application, ApplicationEvent, Document, Job, Profile, User
from app.llm.deps import get_llm
from app.llm.schemas import JobModel, ProfileModel
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


def _seed_user(db_session, email: str) -> User:
    user = User(email=email, password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _seed_job(db_session, user_id: str) -> Job:
    job = Job(
        user_id=user_id,
        source_url="https://example.com/job",
        raw_text="raw text",
        parsed={"company": "Acme", "title": "Engineer", "location": "Remote"},
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def _seed_profile(db_session, user_id: str) -> Profile:
    data = ProfileModel(summary="Experienced engineer.").model_dump()
    profile = Profile(user_id=user_id, version=1, data=data)
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


def _seed_document(db_session, user_id: str, job_id: str, doc_type: str, version: int = 1) -> Document:
    doc = Document(
        user_id=user_id,
        job_id=job_id,
        type=doc_type,
        source_text="cv:\n  name: Test\n",
        version=version,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


class TestAutoCreateOnIngest:
    def test_job_creation_auto_creates_draft_application(self, client, db_session):
        fake_response = MagicMock()
        fake_response.parsed = JobModel(
            company="Acme Corp",
            title="Engineer",
            location="Remote",
            responsibilities=[],
            must_have=[],
            nice_to_have=[],
            keywords=[],
            why_opened_guess="",
            seniority="mid",
            company_type="startup",
            team_name="",
            team_description="",
        )
        fake_llm = MagicMock()
        fake_llm.invoke = AsyncMock(return_value=fake_response)
        app.dependency_overrides[get_llm] = lambda: fake_llm
        try:
            _signup(client, "a@example.com")
            with patch("app.api.jobs.fetch_job_text", return_value="job text"):
                r = client.post("/api/jobs", json={"url": "https://example.com/job"})
            assert r.status_code == 201, r.text
            job_id = r.json()["job"]["id"]

            apps = db_session.query(Application).filter_by(job_id=job_id).all()
            assert len(apps) == 1
            assert apps[0].stage == "Draft"
        finally:
            app.dependency_overrides.pop(get_llm, None)

    def test_backfill_creates_application_for_preexisting_job(self, db_session):
        user = _seed_user(db_session, "pre@example.com")
        job = _seed_job(db_session, user.id)

        assert db_session.query(Application).filter_by(job_id=job.id).first() is None
        created = backfill_applications(db_session)
        assert created == 1
        row = db_session.query(Application).filter_by(job_id=job.id).first()
        assert row is not None
        assert row.stage == "Draft"

    def test_backfill_is_idempotent(self, db_session):
        user = _seed_user(db_session, "pre2@example.com")
        _seed_job(db_session, user.id)

        first = backfill_applications(db_session)
        second = backfill_applications(db_session)
        assert first == 1
        assert second == 0


class TestPublicApi:
    def test_list_applications(self, client, db_session):
        user = _signup(client, "a@example.com")
        job = _seed_job(db_session, user["id"])
        get_or_create_application(db_session, job)

        r = client.get("/api/applications")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["job_id"] == job.id
        assert body[0]["company"] == "Acme"
        assert body[0]["title"] == "Engineer"
        assert body[0]["stage"] == "Draft"

    def test_list_filtered_by_job_id(self, client, db_session):
        user = _signup(client, "a@example.com")
        job1 = _seed_job(db_session, user["id"])
        job2 = _seed_job(db_session, user["id"])
        get_or_create_application(db_session, job1)
        get_or_create_application(db_session, job2)

        r = client.get(f"/api/applications?job_id={job1.id}")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["job_id"] == job1.id

    def test_get_application_detail(self, client, db_session):
        user = _signup(client, "a@example.com")
        job = _seed_job(db_session, user["id"])
        application = get_or_create_application(db_session, job)

        r = client.get(f"/api/applications/{application.id}")
        assert r.status_code == 200
        body = r.json()
        assert body["events"] == []
        assert body["documents"] == []

    def test_get_nonexistent_404(self, client):
        _signup(client, "a@example.com")
        r = client.get("/api/applications/no-such-id")
        assert r.status_code == 404

    def test_unauthenticated_401(self, client):
        r = client.get("/api/applications")
        assert r.status_code == 401

    def test_patch_stage_records_event(self, client, db_session):
        user = _signup(client, "a@example.com")
        job = _seed_job(db_session, user["id"])
        application = get_or_create_application(db_session, job)

        r = client.patch(
            f"/api/applications/{application.id}", json={"stage": "Recruiter Screen"}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["stage"] == "Recruiter Screen"
        assert len(body["events"]) == 1
        assert body["events"][0]["from_stage"] == "Draft"
        assert body["events"][0]["to_stage"] == "Recruiter Screen"

    def test_patch_invalid_stage_422(self, client, db_session):
        user = _signup(client, "a@example.com")
        job = _seed_job(db_session, user["id"])
        application = get_or_create_application(db_session, job)

        r = client.patch(f"/api/applications/{application.id}", json={"stage": "Nonsense"})
        assert r.status_code == 422

    def test_patch_next_action_and_notes(self, client, db_session):
        user = _signup(client, "a@example.com")
        job = _seed_job(db_session, user["id"])
        application = get_or_create_application(db_session, job)

        r = client.patch(
            f"/api/applications/{application.id}",
            json={"next_action": "Follow up Friday", "notes": "Referred by Jane"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["next_action"] == "Follow up Friday"
        assert body["notes"] == "Referred by Jane"


class TestSubmit:
    def test_submit_finalizes_latest_cv_and_letter(self, client, db_session):
        user = _signup(client, "a@example.com")
        job = _seed_job(db_session, user["id"])
        application = get_or_create_application(db_session, job)
        cv_v1 = _seed_document(db_session, user["id"], job.id, "cv", version=1)
        cv_v2 = _seed_document(db_session, user["id"], job.id, "cv", version=2)
        letter = _seed_document(db_session, user["id"], job.id, "cover_letter", version=1)

        r = client.post(f"/api/applications/{application.id}/submit")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["missing_documents"] == []
        assert body["application"]["stage"] == "Applied"
        assert body["application"]["submitted_at"] is not None

        db_session.refresh(cv_v1)
        db_session.refresh(cv_v2)
        db_session.refresh(letter)
        assert cv_v1.is_finalized is False
        assert cv_v2.is_finalized is True
        assert letter.is_finalized is True

        db_session.refresh(application)
        finalized_ids = {d.document_id for d in application.documents}
        assert finalized_ids == {cv_v2.id, letter.id}

    def test_submit_without_documents_reports_missing(self, client, db_session):
        user = _signup(client, "a@example.com")
        job = _seed_job(db_session, user["id"])
        application = get_or_create_application(db_session, job)

        r = client.post(f"/api/applications/{application.id}/submit")
        assert r.status_code == 200
        assert set(r.json()["missing_documents"]) == {"cv", "cover_letter"}

    def test_submit_idempotent_no_duplicate_snapshot(self, client, db_session):
        user = _signup(client, "a@example.com")
        job = _seed_job(db_session, user["id"])
        application = get_or_create_application(db_session, job)
        _seed_document(db_session, user["id"], job.id, "cv", version=1)

        r1 = client.post(f"/api/applications/{application.id}/submit")
        r2 = client.post(f"/api/applications/{application.id}/submit")
        assert r1.status_code == 200
        assert r2.status_code == 200

        db_session.refresh(application)
        assert len(application.documents) == 1


class TestInternalApi:
    def test_missing_secret_rejected(self, client):
        r = client.post("/internal/applications/status", json={"user_id": "u", "job_id": "j"})
        assert r.status_code == 403

        r2 = client.post(
            "/internal/applications/set-stage",
            json={"user_id": "u", "job_id": "j", "stage": "Applied"},
        )
        assert r2.status_code == 403

    def test_status_autocreates_and_reports_draft(self, client, db_session):
        user = _signup(client, "a@example.com")
        job = _seed_job(db_session, user["id"])

        r = client.post(
            "/internal/applications/status",
            json={"user_id": user["id"], "job_id": job.id},
            headers=_headers(),
        )
        assert r.status_code == 200
        assert "Draft" in r.json()["summary"]

    def test_status_missing_job_404(self, client):
        user = _signup(client, "a@example.com")
        r = client.post(
            "/internal/applications/status",
            json={"user_id": user["id"], "job_id": "no-such-job"},
            headers=_headers(),
        )
        assert r.status_code == 404

    def test_set_stage_transitions_and_snapshots(self, client, db_session):
        user = _signup(client, "a@example.com")
        job = _seed_job(db_session, user["id"])
        _seed_document(db_session, user["id"], job.id, "cv", version=1)

        r = client.post(
            "/internal/applications/set-stage",
            json={"user_id": user["id"], "job_id": job.id, "stage": "Applied"},
            headers=_headers(),
        )
        assert r.status_code == 200, r.text
        assert r.json()["stage"] == "Applied"

        application = db_session.query(Application).filter_by(job_id=job.id).first()
        assert application.submitted_at is not None
        assert len(application.documents) == 1  # only the drafted cv, no letter

    def test_set_stage_invalid_422(self, client, db_session):
        user = _signup(client, "a@example.com")
        job = _seed_job(db_session, user["id"])

        r = client.post(
            "/internal/applications/set-stage",
            json={"user_id": user["id"], "job_id": job.id, "stage": "Nonsense"},
            headers=_headers(),
        )
        assert r.status_code == 422

    def test_set_stage_missing_job_404(self, client):
        user = _signup(client, "a@example.com")
        r = client.post(
            "/internal/applications/set-stage",
            json={"user_id": user["id"], "job_id": "no-such-job", "stage": "Applied"},
            headers=_headers(),
        )
        assert r.status_code == 404


class TestAutomation:
    def test_idle_active_application_marked_stale(self, db_session):
        user = _seed_user(db_session, "stale@example.com")
        job = _seed_job(db_session, user.id)
        application = get_or_create_application(db_session, job)
        application, _ = transition_stage(db_session, application, "Applied", actor="user")

        application.last_activity_at = datetime.now(timezone.utc) - timedelta(days=16)
        db_session.commit()

        apply_automation(db_session, datetime.now(timezone.utc))
        db_session.refresh(application)
        assert application.stage == "Stale"
        events = db_session.query(ApplicationEvent).filter_by(application_id=application.id).all()
        assert any(e.to_stage == "Stale" for e in events)

    def test_idle_past_reject_threshold_marked_rejected(self, db_session):
        user = _seed_user(db_session, "reject@example.com")
        job = _seed_job(db_session, user.id)
        application = get_or_create_application(db_session, job)
        application, _ = transition_stage(db_session, application, "Applied", actor="user")

        application.last_activity_at = datetime.now(timezone.utc) - timedelta(days=31)
        db_session.commit()

        apply_automation(db_session, datetime.now(timezone.utc))
        db_session.refresh(application)
        assert application.stage == "Rejected"

    def test_stale_application_eventually_rejected(self, db_session):
        user = _seed_user(db_session, "stale2reject@example.com")
        job = _seed_job(db_session, user.id)
        application = get_or_create_application(db_session, job)
        application, _ = transition_stage(db_session, application, "Applied", actor="user")
        application, _ = transition_stage(db_session, application, "Stale", actor="automation")

        application.last_activity_at = datetime.now(timezone.utc) - timedelta(days=31)
        db_session.commit()

        apply_automation(db_session, datetime.now(timezone.utc))
        db_session.refresh(application)
        assert application.stage == "Rejected"

    def test_draft_application_untouched_by_automation(self, db_session):
        user = _seed_user(db_session, "draft@example.com")
        job = _seed_job(db_session, user.id)
        application = get_or_create_application(db_session, job)
        application.last_activity_at = datetime.now(timezone.utc) - timedelta(days=100)
        db_session.commit()

        apply_automation(db_session, datetime.now(timezone.utc))
        db_session.refresh(application)
        assert application.stage == "Draft"

    def test_terminal_stage_untouched_by_automation(self, db_session):
        user = _seed_user(db_session, "terminal@example.com")
        job = _seed_job(db_session, user.id)
        application = get_or_create_application(db_session, job)
        application, _ = transition_stage(db_session, application, "Accepted", actor="user")
        application.last_activity_at = datetime.now(timezone.utc) - timedelta(days=100)
        db_session.commit()

        apply_automation(db_session, datetime.now(timezone.utc))
        db_session.refresh(application)
        assert application.stage == "Accepted"

    def test_automation_does_not_reset_last_activity(self, db_session):
        """The automation's own stage write must not reset last_activity_at —
        otherwise a Stale application would never reach the reject threshold
        (the clock it's supposed to be advancing would keep getting pushed
        back by the automation's own transition_stage call)."""
        user = _seed_user(db_session, "clock@example.com")
        job = _seed_job(db_session, user.id)
        application = get_or_create_application(db_session, job)
        application, _ = transition_stage(db_session, application, "Applied", actor="user")
        backdated = datetime.now(timezone.utc) - timedelta(days=16)
        application.last_activity_at = backdated
        db_session.commit()

        apply_automation(db_session, datetime.now(timezone.utc))
        db_session.refresh(application)
        assert application.stage == "Stale"
        reloaded = application.last_activity_at.replace(tzinfo=timezone.utc)
        assert abs((reloaded - backdated).total_seconds()) < 2


class TestIsolationAndCascade:
    def test_user_b_cannot_see_user_a_applications(self, client, db_session):
        user_a = _signup(client, "a@example.com")
        job = _seed_job(db_session, user_a["id"])
        application = get_or_create_application(db_session, job)

        client.post("/api/auth/logout")
        _signup(client, "b@example.com")

        assert client.get("/api/applications").json() == []
        assert client.get(f"/api/applications/{application.id}").status_code == 404
        assert (
            client.patch(f"/api/applications/{application.id}", json={"stage": "Applied"}).status_code
            == 404
        )
        assert client.post(f"/api/applications/{application.id}/submit").status_code == 404

    def test_internal_status_scoped_to_user_id_in_body(self, client, db_session):
        user_a = _signup(client, "a@example.com")
        job = _seed_job(db_session, user_a["id"])
        _signup(client, "b@example.com")
        user_b_id = db_session.query(User).filter_by(email="b@example.com").first().id

        r = client.post(
            "/internal/applications/status",
            json={"user_id": user_b_id, "job_id": job.id},
            headers=_headers(),
        )
        assert r.status_code == 404

    def test_job_delete_cascades_to_application(self, client, db_session):
        user = _signup(client, "a@example.com")
        job = _seed_job(db_session, user["id"])
        application = get_or_create_application(db_session, job)
        app_id = application.id

        r = client.delete(f"/api/jobs/{job.id}")
        assert r.status_code == 204
        assert db_session.query(Application).filter_by(id=app_id).first() is None

    def test_user_delete_cascades_to_application(self, db_session):
        user = _seed_user(db_session, "todelete@example.com")
        job = _seed_job(db_session, user.id)
        application = get_or_create_application(db_session, job)
        app_id = application.id

        db_session.delete(user)
        db_session.commit()
        assert db_session.query(Application).filter_by(id=app_id).first() is None
