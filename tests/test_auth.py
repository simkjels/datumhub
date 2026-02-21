"""Tests for /api/auth endpoints."""

from __future__ import annotations


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
