"""Tests for /api/v1/users endpoints."""

from __future__ import annotations

VALID_PKG = {
    "id": "testuser/samples/sampledata",
    "version": "0.1.0",
    "title": "Sample Data",
    "publisher": {"name": "Test Publisher"},
    "sources": [{"url": "https://example.com/sample.csv", "format": "csv"}],
}


class TestGetMe:
    def test_requires_auth(self, client):
        resp = client.get("/api/v1/users/me")
        assert resp.status_code == 401

    def test_returns_200_when_authenticated(self, auth_client):
        resp = auth_client.get("/api/v1/users/me")
        assert resp.status_code == 200

    def test_returns_own_username(self, auth_client):
        data = auth_client.get("/api/v1/users/me").json()
        assert data["username"] == "testuser"

    def test_joined_at_present(self, auth_client):
        data = auth_client.get("/api/v1/users/me").json()
        assert "joined_at" in data
        assert data["joined_at"]

    def test_package_count_zero_initially(self, auth_client):
        data = auth_client.get("/api/v1/users/me").json()
        assert data["package_count"] == 0
        assert data["packages"] == []

    def test_package_count_reflects_published(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        data = auth_client.get("/api/v1/users/me").json()
        assert data["package_count"] == 1
        assert len(data["packages"]) == 1

    def test_packages_contain_published_id(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        data = auth_client.get("/api/v1/users/me").json()
        assert data["packages"][0]["id"] == VALID_PKG["id"]


class TestGetUser:
    def test_unknown_user_returns_404(self, client):
        resp = client.get("/api/v1/users/nobody")
        assert resp.status_code == 404

    def test_known_user_returns_200(self, auth_client):
        resp = auth_client.get("/api/v1/users/testuser")
        assert resp.status_code == 200

    def test_returns_username(self, auth_client):
        data = auth_client.get("/api/v1/users/testuser").json()
        assert data["username"] == "testuser"

    def test_returns_joined_at(self, auth_client):
        data = auth_client.get("/api/v1/users/testuser").json()
        assert "joined_at" in data

    def test_returns_published_packages(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        data = auth_client.get("/api/v1/users/testuser").json()
        assert data["package_count"] == 1
        assert data["packages"][0]["id"] == VALID_PKG["id"]

    def test_is_public_no_auth_needed(self, client, auth_client):
        # Register and publish as auth_client, then fetch without auth
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        resp = client.get("/api/v1/users/testuser")
        assert resp.status_code == 200
        assert resp.json()["package_count"] == 1

    def test_me_route_not_captured_as_username(self, auth_client):
        # /me should return 401/200 (authenticated route), not 404 (username lookup)
        resp = auth_client.get("/api/v1/users/me")
        assert resp.status_code == 200
        assert "username" in resp.json()
