"""M5 profile version history — snapshotting, agent-write debounce, prune, restore."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db.models import Profile, ProfileVersion
from app.llm.schemas import ProfileModel

_SECRET = "test-internal-secret"


@pytest.fixture(autouse=True)
def _internal_secret(monkeypatch):
    monkeypatch.setenv("AGENT_INTERNAL_SECRET", _SECRET)


def _headers() -> dict:
    return {"X-Internal-Secret": _SECRET}


def _signup(client, email: str, password: str = "password123") -> dict:
    r = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


def _seed_profile(db_session, user_id: str, summary: str = "Original summary.") -> Profile:
    data = ProfileModel(summary=summary).model_dump()
    profile = Profile(user_id=user_id, version=1, data=data)
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


class TestUserSaveSnapshots:
    def test_put_profile_snapshots_before_change(self, client, db_session):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"], "Original summary.")

        body = ProfileModel(summary="Updated summary.").model_dump()
        r = client.put("/api/profile", json=body)
        assert r.status_code == 200, r.text

        versions = db_session.query(ProfileVersion).filter_by(user_id=user["id"]).all()
        assert len(versions) == 1
        assert versions[0].source == "user"
        assert versions[0].data["summary"] == "Original summary."

    def test_consecutive_user_saves_each_snapshot(self, client, db_session):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"], "v1")

        client.put("/api/profile", json=ProfileModel(summary="v2").model_dump())
        client.put("/api/profile", json=ProfileModel(summary="v3").model_dump())

        versions = db_session.query(ProfileVersion).filter_by(user_id=user["id"]).all()
        assert len(versions) == 2
        summaries = {v.data["summary"] for v in versions}
        assert summaries == {"v1", "v2"}


class TestAgentWriteDebounce:
    def test_agent_write_creates_snapshot(self, client, db_session):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"], "Original.")

        r = client.post(
            "/internal/profile/update-section",
            json={"user_id": user["id"], "section": "summary", "value": "Agent edit 1"},
            headers=_headers(),
        )
        assert r.status_code == 200

        versions = db_session.query(ProfileVersion).filter_by(user_id=user["id"]).all()
        assert len(versions) == 1
        assert versions[0].source == "agent"
        assert versions[0].data["summary"] == "Original."

    def test_consecutive_agent_writes_within_window_coalesce(self, client, db_session):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"], "Original.")

        client.post(
            "/internal/profile/update-section",
            json={"user_id": user["id"], "section": "summary", "value": "Agent edit 1"},
            headers=_headers(),
        )
        client.post(
            "/internal/profile/add-item",
            json={
                "user_id": user["id"],
                "section": "skills",
                "item": {"label": "Languages", "details": "Python"},
            },
            headers=_headers(),
        )
        client.post(
            "/internal/profile/update-section",
            json={"user_id": user["id"], "section": "summary", "value": "Agent edit 3"},
            headers=_headers(),
        )

        versions = db_session.query(ProfileVersion).filter_by(user_id=user["id"]).all()
        # One conversation's burst of agent writes = one undo step.
        assert len(versions) == 1
        assert versions[0].data["summary"] == "Original."

    def test_agent_write_outside_window_creates_new_snapshot(self, client, db_session):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"], "Original.")

        client.post(
            "/internal/profile/update-section",
            json={"user_id": user["id"], "section": "summary", "value": "Agent edit 1"},
            headers=_headers(),
        )
        # Simulate the debounce window having elapsed.
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=20)
        db_session.query(ProfileVersion).filter_by(user_id=user["id"]).update(
            {"created_at": stale_time}
        )
        db_session.commit()

        client.post(
            "/internal/profile/update-section",
            json={"user_id": user["id"], "section": "summary", "value": "Agent edit 2"},
            headers=_headers(),
        )

        versions = (
            db_session.query(ProfileVersion)
            .filter_by(user_id=user["id"])
            .order_by(ProfileVersion.created_at)
            .all()
        )
        assert len(versions) == 2
        assert versions[0].data["summary"] == "Original."
        assert versions[1].data["summary"] == "Agent edit 1"

    def test_user_save_interleaved_with_agent_writes_creates_separate_snapshots(
        self, client, db_session
    ):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"], "Original.")

        client.post(
            "/internal/profile/update-section",
            json={"user_id": user["id"], "section": "summary", "value": "Agent edit"},
            headers=_headers(),
        )
        client.put("/api/profile", json=ProfileModel(summary="User edit").model_dump())
        client.post(
            "/internal/profile/update-section",
            json={"user_id": user["id"], "section": "summary", "value": "Agent edit 2"},
            headers=_headers(),
        )

        versions = (
            db_session.query(ProfileVersion)
            .filter_by(user_id=user["id"])
            .order_by(ProfileVersion.created_at)
            .all()
        )
        assert [v.source for v in versions] == ["agent", "user", "agent"]
        assert versions[1].data["summary"] == "Agent edit"


class TestPrune:
    def test_prunes_to_max_versions(self, client, db_session, monkeypatch):
        monkeypatch.setattr("app.db.profile_history.profile_history_max_versions", lambda: 3)
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"], "v0")

        for i in range(1, 6):
            client.put("/api/profile", json=ProfileModel(summary=f"v{i}").model_dump())

        versions = db_session.query(ProfileVersion).filter_by(user_id=user["id"]).all()
        assert len(versions) == 3


class TestListAndRestore:
    def test_list_versions_excludes_data_payload(self, client, db_session):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"], "Original.")
        client.put("/api/profile", json=ProfileModel(summary="Updated").model_dump())

        r = client.get("/api/profile/versions")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert "data" not in body[0]
        assert body[0]["source"] == "user"

    def test_restore_applies_old_data_as_new_version(self, client, db_session):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"], "Original.")
        client.put("/api/profile", json=ProfileModel(summary="Updated").model_dump())

        versions = client.get("/api/profile/versions").json()
        version_id = versions[0]["id"]

        r = client.post(f"/api/profile/versions/{version_id}/restore")
        assert r.status_code == 200, r.text
        assert r.json()["data"]["summary"] == "Original."
        assert r.json()["version"] == 3  # v1 -> v2 (update) -> v3 (restore)

    def test_restore_is_itself_undoable(self, client, db_session):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"], "Original.")
        client.put("/api/profile", json=ProfileModel(summary="Updated").model_dump())

        versions = client.get("/api/profile/versions").json()
        version_id = versions[0]["id"]
        client.post(f"/api/profile/versions/{version_id}/restore")

        # A version snapshotting "Updated" (the state right before the restore)
        # must now exist, so the restore itself can be undone.
        all_versions = db_session.query(ProfileVersion).filter_by(user_id=user["id"]).all()
        summaries = {v.data["summary"] for v in all_versions}
        assert "Updated" in summaries
        assert any(v.source == "restore" for v in all_versions)

    def test_restore_nonexistent_version_404(self, client, db_session):
        user = _signup(client, "a@example.com")
        _seed_profile(db_session, user["id"])

        r = client.post("/api/profile/versions/no-such-id/restore")
        assert r.status_code == 404


class TestIsolation:
    def test_user_b_cannot_list_user_a_versions(self, client, db_session):
        user_a = _signup(client, "a@example.com")
        _seed_profile(db_session, user_a["id"], "Original.")
        client.put("/api/profile", json=ProfileModel(summary="Updated").model_dump())

        client.post("/api/auth/logout")
        _signup(client, "b@example.com")

        r = client.get("/api/profile/versions")
        assert r.status_code == 200
        assert r.json() == []

    def test_user_b_cannot_restore_user_a_version(self, client, db_session):
        user_a = _signup(client, "a@example.com")
        _seed_profile(db_session, user_a["id"], "Original.")
        client.put("/api/profile", json=ProfileModel(summary="Updated").model_dump())
        versions = client.get("/api/profile/versions").json()
        version_id = versions[0]["id"]

        client.post("/api/auth/logout")
        _signup(client, "b@example.com")

        r = client.post(f"/api/profile/versions/{version_id}/restore")
        assert r.status_code == 404
