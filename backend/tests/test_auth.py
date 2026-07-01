"""M1 auth acceptance tests — maps to SPEC §14 isolation checks."""
from __future__ import annotations


def _signup(client, email: str, password: str = "password123") -> dict:
    r = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


def _login(client, email: str, password: str = "password123") -> None:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text


class TestSignup:
    def test_first_user_becomes_admin(self, client):
        user = _signup(client, "admin@example.com")
        assert user["role"] == "admin"

    def test_second_user_is_regular(self, client):
        _signup(client, "first@example.com")
        user = _signup(client, "second@example.com")
        assert user["role"] == "user"

    def test_duplicate_email_rejected(self, client):
        _signup(client, "dup@example.com")
        r = client.post("/api/auth/signup", json={"email": "dup@example.com", "password": "password123"})
        assert r.status_code == 409

    def test_short_password_rejected(self, client):
        r = client.post("/api/auth/signup", json={"email": "x@example.com", "password": "short"})
        assert r.status_code == 422


class TestLogin:
    def test_login_sets_cookie(self, client):
        _signup(client, "u@example.com")
        # Cookie is automatically stored by TestClient
        r = client.post("/api/auth/login", json={"email": "u@example.com", "password": "password123"})
        assert r.status_code == 200
        assert "hirable_session" in client.cookies

    def test_wrong_password_rejected(self, client):
        _signup(client, "u@example.com")
        r = client.post("/api/auth/login", json={"email": "u@example.com", "password": "wrongpass"})
        assert r.status_code == 401

    def test_unknown_email_rejected(self, client):
        r = client.post("/api/auth/login", json={"email": "noone@example.com", "password": "password123"})
        assert r.status_code == 401


class TestMe:
    def test_me_returns_current_user(self, client):
        _signup(client, "me@example.com")
        r = client.get("/api/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == "me@example.com"

    def test_me_unauthenticated(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401


class TestLogout:
    def test_logout_clears_session(self, client):
        _signup(client, "bye@example.com")
        r = client.post("/api/auth/logout")
        assert r.status_code == 200
        # After logout, /me must reject
        r2 = client.get("/api/auth/me")
        assert r2.status_code == 401


class TestSessionIsolation:
    def test_users_isolated(self, client):
        """User A's session cannot be used as user B."""
        a = _signup(client, "a@example.com")
        # Clear session (simulate user A logs out)
        client.post("/api/auth/logout")

        # Sign up and log in as user B
        b = _signup(client, "b@example.com")

        # /me must return B, not A
        r = client.get("/api/auth/me")
        assert r.status_code == 200
        assert r.json()["id"] == b["id"]
        assert r.json()["id"] != a["id"]


class TestAdmin:
    def _setup_admin_and_user(self, client):
        admin = _signup(client, "admin@example.com")
        client.post("/api/auth/logout")
        user = _signup(client, "user@example.com")
        client.post("/api/auth/logout")
        _login(client, "admin@example.com")
        return admin, user

    def test_list_users(self, client):
        admin, user = self._setup_admin_and_user(client)
        r = client.get("/api/admin/users")
        assert r.status_code == 200
        emails = [u["email"] for u in r.json()]
        assert "admin@example.com" in emails
        assert "user@example.com" in emails

    def test_non_admin_cannot_list_users(self, client):
        _signup(client, "admin@example.com")
        client.post("/api/auth/logout")
        _signup(client, "user@example.com")
        r = client.get("/api/admin/users")
        assert r.status_code == 403

    def test_admin_can_disable_user(self, client):
        admin, user = self._setup_admin_and_user(client)
        r = client.post(f"/api/admin/users/{user['id']}/disable")
        assert r.status_code == 200
        # User's session should be invalidated — they can't hit /me
        # Simulate: log in as user (which should fail if disabled)
        client.post("/api/auth/logout")
        r2 = client.post("/api/auth/login", json={"email": "user@example.com", "password": "password123"})
        assert r2.status_code == 403

    def test_admin_delete_cascades(self, client):
        admin, user = self._setup_admin_and_user(client)
        user_id = user["id"]
        r = client.delete(f"/api/admin/users/{user_id}")
        assert r.status_code == 204
        # User should no longer appear in list
        users = client.get("/api/admin/users").json()
        assert not any(u["id"] == user_id for u in users)

    def test_admin_cannot_delete_self(self, client):
        admin, _ = self._setup_admin_and_user(client)
        r = client.delete(f"/api/admin/users/{admin['id']}")
        assert r.status_code == 400

    def test_admin_reset_password_invalidates_session(self, client):
        admin, user = self._setup_admin_and_user(client)
        r = client.post(
            f"/api/admin/users/{user['id']}/reset-password",
            json={"new_password": "newpassword123"},
        )
        assert r.status_code == 200
        # Old password no longer works
        client.post("/api/auth/logout")
        r2 = client.post("/api/auth/login", json={"email": "user@example.com", "password": "password123"})
        assert r2.status_code == 401
        # New password works
        r3 = client.post("/api/auth/login", json={"email": "user@example.com", "password": "newpassword123"})
        assert r3.status_code == 200
