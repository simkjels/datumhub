"""Tests for /api/auth endpoints."""

from __future__ import annotations

import datumhub.database as db_module


class TestRegister:
    def test_register_returns_201(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "password123"},
        )
        assert resp.status_code == 201

    def test_register_returns_username(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "password123"},
        )
        assert resp.json()["username"] == "alice"
        assert resp.json()["registered"] is True

    def test_duplicate_username_returns_409(self, client):
        payload = {"username": "alice", "password": "password123"}
        client.post("/api/auth/register", json=payload)
        resp = client.post("/api/auth/register", json=payload)
        assert resp.status_code == 409

    def test_short_password_returns_422(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "short"},
        )
        assert resp.status_code == 422

    def test_invalid_username_returns_422(self, client):
        resp = client.post(
            "/api/auth/register",
            json={"username": "Alice!", "password": "password123"},
        )
        assert resp.status_code == 422


class TestGetToken:
    def test_valid_credentials_return_token(self, client):
        client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "password123"},
        )
        resp = client.post(
            "/api/auth/token",
            json={"username": "alice", "password": "password123"},
        )
        assert resp.status_code == 200
        assert "token" in resp.json()
        assert len(resp.json()["token"]) == 64  # 32 hex bytes

    def test_wrong_password_returns_401(self, client):
        client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "password123"},
        )
        resp = client.post(
            "/api/auth/token",
            json={"username": "alice", "password": "wrongpass"},
        )
        assert resp.status_code == 401

    def test_unknown_user_returns_401(self, client):
        resp = client.post(
            "/api/auth/token",
            json={"username": "nobody", "password": "password123"},
        )
        assert resp.status_code == 401

    def test_multiple_logins_give_different_tokens(self, client):
        client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "password123"},
        )
        creds = {"username": "alice", "password": "password123"}
        t1 = client.post("/api/auth/token", json=creds).json()["token"]
        t2 = client.post("/api/auth/token", json=creds).json()["token"]
        assert t1 != t2


class TestTokenExpiry:
    def test_valid_token_authenticates(self, auth_client):
        """A freshly issued token works."""
        resp = auth_client.get("/api/v1/users/me")
        assert resp.status_code == 200

    def test_expired_token_returns_401(self, client):
        """A token whose expires_at is in the past is rejected."""
        client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "password123"},
        )
        resp = client.post(
            "/api/auth/token",
            json={"username": "alice", "password": "password123"},
        )
        token = resp.json()["token"]

        # Manually expire the token by updating the DB directly
        db = db_module.get_db()
        db.execute(
            "UPDATE api_tokens SET expires_at = datetime('now', '-1 second') WHERE token = ?",
            (token,),
        )
        db.commit()

        resp = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    def test_new_tokens_have_expires_at(self, client):
        """Tokens issued via /api/auth/token include an expires_at in the DB."""
        client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "password123"},
        )
        resp = client.post(
            "/api/auth/token",
            json={"username": "alice", "password": "password123"},
        )
        token = resp.json()["token"]

        db = db_module.get_db()
        row = db.execute(
            "SELECT expires_at FROM api_tokens WHERE token = ?", (token,)
        ).fetchone()
        assert row is not None
        assert row["expires_at"] is not None


class TestRefreshToken:
    def test_refresh_returns_new_token(self, auth_client):
        resp = auth_client.post("/api/auth/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert len(data["token"]) == 64

    def test_refreshed_token_is_different(self, auth_client):
        old_token = auth_client.headers["Authorization"].split(" ")[1]
        new_token = auth_client.post("/api/auth/refresh").json()["token"]
        assert old_token != new_token

    def test_refreshed_token_works(self, auth_client):
        new_token = auth_client.post("/api/auth/refresh").json()["token"]
        resp = auth_client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {new_token}"},
        )
        assert resp.status_code == 200

    def test_refresh_without_token_returns_401(self, client):
        resp = client.post("/api/auth/refresh")
        assert resp.status_code == 401

    def test_refresh_with_expired_token_returns_401(self, client):
        client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "password123"},
        )
        resp = client.post(
            "/api/auth/token",
            json={"username": "alice", "password": "password123"},
        )
        token = resp.json()["token"]

        # Expire the token
        db = db_module.get_db()
        db.execute(
            "UPDATE api_tokens SET expires_at = datetime('now', '-1 second') WHERE token = ?",
            (token,),
        )
        db.commit()

        resp = client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
