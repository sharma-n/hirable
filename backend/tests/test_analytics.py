"""M8 analytics dashboard — funnel, response rate (incl. ghosting exclusion),
median time-to-response, applications-over-time, status counts, offer rate,
per-CV-version performance, company-type/location breakdowns, isolation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.analytics.service import _is_response_event, _median_days, _pct
from app.applications.service import get_or_create_application, transition_stage
from app.db.models import Document, Job, User

_SECRET = "test-internal-secret"


@pytest.fixture(autouse=True)
def _internal_secret(monkeypatch):
    monkeypatch.setenv("AGENT_INTERNAL_SECRET", _SECRET)


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


def _seed_job(db_session, user_id: str, parsed: dict | None = None) -> Job:
    job = Job(
        user_id=user_id,
        source_url="https://example.com/job",
        raw_text="raw text",
        parsed=parsed if parsed is not None else {"company": "Acme", "title": "Engineer", "location": "Remote"},
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


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


def _backdate_submitted(db_session, application, days: int) -> None:
    application.submitted_at = datetime.now(timezone.utc) - timedelta(days=days)
    db_session.commit()


class TestEmptyState:
    def test_zero_applications(self, client, db_session):
        _signup(client, "a@example.com")
        r = client.get("/api/analytics")
        assert r.status_code == 200
        body = r.json()
        assert body["response_rate"] == 0.0
        assert body["offer_rate"] == 0.0
        assert body["median_time_to_first_response_days"] is None
        assert all(stage["count"] == 0 for stage in body["funnel"])
        assert all(count == 0 for count in body["status_counts"]["by_stage"].values())
        assert body["status_counts"]["active"] == 0
        assert body["applications_over_time"] == []
        assert body["cv_version_performance"] == []
        assert body["by_company_type"] == []
        assert body["by_location"] == []

    def test_unauthenticated_401(self, client):
        r = client.get("/api/analytics")
        assert r.status_code == 401


class TestFunnel:
    def test_counts_and_pct(self, client, db_session):
        user = _signup(client, "a@example.com")

        # Never submitted — excluded entirely.
        _seed_job(db_session, user["id"])

        # Applied only.
        job2 = _seed_job(db_session, user["id"])
        app2 = get_or_create_application(db_session, job2)
        transition_stage(db_session, app2, "Applied", actor="user")

        # Applied -> Recruiter Screen -> Technical.
        job3 = _seed_job(db_session, user["id"])
        app3 = get_or_create_application(db_session, job3)
        transition_stage(db_session, app3, "Applied", actor="user")
        transition_stage(db_session, app3, "Recruiter Screen", actor="user")
        transition_stage(db_session, app3, "Technical", actor="user")

        r = client.get("/api/analytics")
        assert r.status_code == 200
        funnel = {s["stage"]: s for s in r.json()["funnel"]}
        assert funnel["Applied"]["count"] == 2
        assert funnel["Applied"]["pct_of_applied"] == 1.0
        assert funnel["Recruiter Screen"]["count"] == 1
        assert funnel["Recruiter Screen"]["pct_of_applied"] == 0.5
        assert funnel["Technical"]["count"] == 1
        assert funnel["Onsite"]["count"] == 0


class TestResponseRate:
    def test_response_detection_excludes_automation_ghosting(self, client, db_session):
        user = _signup(client, "a@example.com")

        # Responded: Applied -> Recruiter Screen.
        job1 = _seed_job(db_session, user["id"])
        app1 = get_or_create_application(db_session, job1)
        transition_stage(db_session, app1, "Applied", actor="user")
        transition_stage(db_session, app1, "Recruiter Screen", actor="user")

        # Responded: Applied -> Rejected, manually (a real rejection reply).
        job2 = _seed_job(db_session, user["id"])
        app2 = get_or_create_application(db_session, job2)
        transition_stage(db_session, app2, "Applied", actor="user")
        transition_stage(db_session, app2, "Rejected", actor="user")

        # NOT responded: Applied -> Stale -> Rejected, via automation (ghosted).
        job3 = _seed_job(db_session, user["id"])
        app3 = get_or_create_application(db_session, job3)
        transition_stage(db_session, app3, "Applied", actor="user")
        transition_stage(db_session, app3, "Stale", actor="automation")
        transition_stage(db_session, app3, "Rejected", actor="automation")

        # NOT responded: Applied only, nothing further.
        job4 = _seed_job(db_session, user["id"])
        app4 = get_or_create_application(db_session, job4)
        transition_stage(db_session, app4, "Applied", actor="user")

        r = client.get("/api/analytics")
        assert r.status_code == 200
        body = r.json()
        assert body["response_rate"] == pytest.approx(2 / 4)


class TestMedianTimeToResponse:
    def test_median_across_responded_applications(self, client, db_session):
        user = _signup(client, "a@example.com")

        job1 = _seed_job(db_session, user["id"])
        app1 = get_or_create_application(db_session, job1)
        transition_stage(db_session, app1, "Applied", actor="user")
        _backdate_submitted(db_session, app1, days=4)
        transition_stage(db_session, app1, "Recruiter Screen", actor="user")

        job2 = _seed_job(db_session, user["id"])
        app2 = get_or_create_application(db_session, job2)
        transition_stage(db_session, app2, "Applied", actor="user")
        _backdate_submitted(db_session, app2, days=10)
        transition_stage(db_session, app2, "Technical", actor="user")

        # Submitted, no response yet — excluded from the median set.
        job3 = _seed_job(db_session, user["id"])
        app3 = get_or_create_application(db_session, job3)
        transition_stage(db_session, app3, "Applied", actor="user")

        r = client.get("/api/analytics")
        assert r.status_code == 200
        median = r.json()["median_time_to_first_response_days"]
        assert median is not None
        assert abs(median - 7) < 0.5  # median of ~4 and ~10 days

    def test_none_when_no_responses(self, client, db_session):
        user = _signup(client, "a@example.com")
        job = _seed_job(db_session, user["id"])
        application = get_or_create_application(db_session, job)
        transition_stage(db_session, application, "Applied", actor="user")

        r = client.get("/api/analytics")
        assert r.json()["median_time_to_first_response_days"] is None


class TestOfferRate:
    def test_offer_rate(self, client, db_session):
        user = _signup(client, "a@example.com")

        job1 = _seed_job(db_session, user["id"])
        app1 = get_or_create_application(db_session, job1)
        transition_stage(db_session, app1, "Applied", actor="user")
        transition_stage(db_session, app1, "Offer", actor="user")

        job2 = _seed_job(db_session, user["id"])
        app2 = get_or_create_application(db_session, job2)
        transition_stage(db_session, app2, "Applied", actor="user")
        transition_stage(db_session, app2, "Recruiter Screen", actor="user")

        r = client.get("/api/analytics")
        assert r.json()["offer_rate"] == pytest.approx(1 / 2)


class TestApplicationsOverTime:
    def test_grouped_by_month(self, client, db_session):
        user = _signup(client, "a@example.com")
        job = _seed_job(db_session, user["id"])
        application = get_or_create_application(db_session, job)
        transition_stage(db_session, application, "Applied", actor="user")

        r = client.get("/api/analytics")
        points = r.json()["applications_over_time"]
        assert len(points) == 1
        assert points[0]["count"] == 1
        assert points[0]["month"] == datetime.now(timezone.utc).strftime("%Y-%m")


class TestCvVersionPerformance:
    def test_grouped_by_finalized_version(self, client, db_session):
        user = _signup(client, "a@example.com")

        # Job A: two CV drafts, v2 is the one finalized at submit time.
        job_a = _seed_job(db_session, user["id"])
        _seed_document(db_session, user["id"], job_a.id, "cv", version=1)
        _seed_document(db_session, user["id"], job_a.id, "cv", version=2)
        app_a = get_or_create_application(db_session, job_a)
        transition_stage(db_session, app_a, "Applied", actor="user")
        transition_stage(db_session, app_a, "Recruiter Screen", actor="user")  # responded

        # Job B: only a v1 CV draft, finalized as-is, no response.
        job_b = _seed_job(db_session, user["id"])
        _seed_document(db_session, user["id"], job_b.id, "cv", version=1)
        app_b = get_or_create_application(db_session, job_b)
        transition_stage(db_session, app_b, "Applied", actor="user")

        # Job C: submitted with no CV draft at all — excluded from this breakdown.
        job_c = _seed_job(db_session, user["id"])
        app_c = get_or_create_application(db_session, job_c)
        transition_stage(db_session, app_c, "Applied", actor="user")

        r = client.get("/api/analytics")
        by_version = {row["version"]: row for row in r.json()["cv_version_performance"]}
        assert set(by_version) == {1, 2}
        assert by_version[2]["submitted_count"] == 1
        assert by_version[2]["response_count"] == 1
        assert by_version[1]["submitted_count"] == 1
        assert by_version[1]["response_count"] == 0


class TestBreakdowns:
    def test_by_company_type_and_location(self, client, db_session):
        user = _signup(client, "a@example.com")

        job1 = _seed_job(
            db_session, user["id"], parsed={"company_type": "startup", "location": "Remote"}
        )
        app1 = get_or_create_application(db_session, job1)
        transition_stage(db_session, app1, "Applied", actor="user")
        transition_stage(db_session, app1, "Recruiter Screen", actor="user")

        job2 = _seed_job(
            db_session, user["id"], parsed={"company_type": "enterprise", "location": "Remote"}
        )
        app2 = get_or_create_application(db_session, job2)
        transition_stage(db_session, app2, "Applied", actor="user")

        # Missing company_type key entirely — falls into "Unknown".
        job3 = _seed_job(db_session, user["id"], parsed={"location": "NYC"})
        app3 = get_or_create_application(db_session, job3)
        transition_stage(db_session, app3, "Applied", actor="user")

        r = client.get("/api/analytics")
        body = r.json()
        by_company_type = {g["key"]: g for g in body["by_company_type"]}
        assert by_company_type["startup"]["count"] == 1
        assert by_company_type["startup"]["response_rate"] == 1.0
        assert by_company_type["enterprise"]["count"] == 1
        assert by_company_type["Unknown"]["count"] == 1

        by_location = {g["key"]: g for g in body["by_location"]}
        assert by_location["Remote"]["count"] == 2
        assert by_location["NYC"]["count"] == 1


class TestIsolation:
    def test_user_b_does_not_see_user_a_data(self, client, db_session):
        user_a = _signup(client, "a@example.com")
        for _ in range(5):
            job = _seed_job(db_session, user_a["id"])
            application = get_or_create_application(db_session, job)
            transition_stage(db_session, application, "Applied", actor="user")

        client.post("/api/auth/logout")
        _signup(client, "b@example.com")
        job_b = _seed_job(db_session, client.get("/api/auth/me").json()["id"])
        application_b = get_or_create_application(db_session, job_b)
        transition_stage(db_session, application_b, "Applied", actor="user")

        r = client.get("/api/analytics")
        assert r.status_code == 200
        body = r.json()
        assert body["status_counts"]["by_stage"]["Applied"] == 1
        assert sum(body["status_counts"]["by_stage"].values()) == 1


class TestPureHelpers:
    def test_pct_guards_division_by_zero(self):
        assert _pct(0, 0) == 0.0
        assert _pct(1, 2) == 0.5

    def test_median_days_empty_is_none(self):
        assert _median_days([]) is None
        assert _median_days([1.0, 3.0]) == 2.0

    def test_is_response_event(self):
        assert _is_response_event("Recruiter Screen", "user") is True
        assert _is_response_event("Rejected", "user") is True
        assert _is_response_event("Rejected", "automation") is False
        assert _is_response_event("Stale", "automation") is False
        assert _is_response_event("Stale", "user") is False
