"""Tests for /api/v1/packages endpoints."""

from __future__ import annotations

VALID_PKG = {
    "id": "simkjels/samples/sampledata",
    "version": "0.1.0",
    "title": "Sample Data",
    "publisher": {"name": "Simen Kjelsrud"},
    "sources": [{"url": "https://example.com/sample.csv", "format": "csv"}],
}


class TestPublish:
    def test_publish_returns_201(self, auth_client):
        resp = auth_client.post("/api/v1/packages", json=VALID_PKG)
        assert resp.status_code == 201

    def test_publish_returns_package(self, auth_client):
        resp = auth_client.post("/api/v1/packages", json=VALID_PKG)
        data = resp.json()
        assert data["id"] == VALID_PKG["id"]
        assert data["version"] == VALID_PKG["version"]
        assert data["owner"] == "testuser"
        assert "published_at" in data

    def test_publish_requires_auth(self, client):
        resp = client.post("/api/v1/packages", json=VALID_PKG)
        assert resp.status_code == 401

    def test_duplicate_returns_409(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        resp = auth_client.post("/api/v1/packages", json=VALID_PKG)
        assert resp.status_code == 409

    def test_force_overwrites(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        resp = auth_client.post("/api/v1/packages?force=true", json=VALID_PKG)
        assert resp.status_code == 201

    def test_invalid_id_returns_422(self, auth_client):
        resp = auth_client.post("/api/v1/packages", json={**VALID_PKG, "id": "bad-id"})
        assert resp.status_code == 422

    def test_empty_sources_returns_422(self, auth_client):
        resp = auth_client.post("/api/v1/packages", json={**VALID_PKG, "sources": []})
        assert resp.status_code == 422


class TestGetPackage:
    def test_get_specific_version(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        resp = auth_client.get(
            f"/api/v1/packages/{VALID_PKG['id']}/{VALID_PKG['version']}"
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == VALID_PKG["id"]

    def test_get_unknown_returns_404(self, client):
        resp = client.get("/api/v1/packages/simkjels/samples/sampledata/9.9.9")
        assert resp.status_code == 404

    def test_get_latest(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        auth_client.post("/api/v1/packages", json={**VALID_PKG, "version": "0.2.0"})
        resp = auth_client.get(f"/api/v1/packages/{VALID_PKG['id']}/latest")
        assert resp.status_code == 200
        assert resp.json()["version"] == "0.2.0"

    def test_get_latest_unknown_returns_404(self, client):
        resp = client.get("/api/v1/packages/simkjels/samples/unknown/latest")
        assert resp.status_code == 404


class TestListPackages:
    def test_empty_registry_returns_empty_list(self, client):
        resp = client.get("/api/v1/packages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_lists_published_package(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        resp = auth_client.get("/api/v1/packages")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == VALID_PKG["id"]

    def test_search_by_title(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        resp = auth_client.get("/api/v1/packages?q=Sample+Data")
        assert resp.json()["total"] == 1

    def test_search_no_match_returns_empty(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        resp = auth_client.get("/api/v1/packages?q=zzznomatch")
        assert resp.json()["total"] == 0

    def test_pagination(self, auth_client):
        for i in range(5):
            auth_client.post(
                "/api/v1/packages",
                json={**VALID_PKG, "version": f"0.{i}.0"},
            )
        resp = auth_client.get("/api/v1/packages?limit=2&offset=0")
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["limit"] == 2


class TestGetAllVersions:
    def test_returns_all_versions(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        auth_client.post("/api/v1/packages", json={**VALID_PKG, "version": "0.2.0"})
        resp = auth_client.get(f"/api/v1/packages/{VALID_PKG['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["versions"]) == 2

    def test_returns_id(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        data = auth_client.get(f"/api/v1/packages/{VALID_PKG['id']}").json()
        assert data["id"] == VALID_PKG["id"]

    def test_newest_version_first(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        auth_client.post("/api/v1/packages", json={**VALID_PKG, "version": "0.2.0"})
        data = auth_client.get(f"/api/v1/packages/{VALID_PKG['id']}").json()
        assert data["versions"][0]["version"] == "0.2.0"

    def test_unknown_package_returns_404(self, client):
        resp = client.get("/api/v1/packages/simkjels/samples/unknown")
        assert resp.status_code == 404


class TestListPagination:
    def test_has_next_true_when_more_results(self, auth_client):
        for i in range(3):
            auth_client.post("/api/v1/packages", json={**VALID_PKG, "version": f"0.{i}.0"})
        data = auth_client.get("/api/v1/packages?limit=2&offset=0").json()
        assert data["has_next"] is True
        assert data["has_prev"] is False

    def test_has_prev_true_on_second_page(self, auth_client):
        for i in range(3):
            auth_client.post("/api/v1/packages", json={**VALID_PKG, "version": f"0.{i}.0"})
        data = auth_client.get("/api/v1/packages?limit=2&offset=2").json()
        assert data["has_prev"] is True
        assert data["has_next"] is False

    def test_no_next_or_prev_on_single_page(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        data = auth_client.get("/api/v1/packages").json()
        assert data["has_next"] is False
        assert data["has_prev"] is False


class TestUnpublish:
    def test_unpublish_returns_204(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        resp = auth_client.delete(
            f"/api/v1/packages/{VALID_PKG['id']}/{VALID_PKG['version']}"
        )
        assert resp.status_code == 204

    def test_unpublish_removes_package(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        auth_client.delete(
            f"/api/v1/packages/{VALID_PKG['id']}/{VALID_PKG['version']}"
        )
        resp = auth_client.get(
            f"/api/v1/packages/{VALID_PKG['id']}/{VALID_PKG['version']}"
        )
        assert resp.status_code == 404

    def test_unpublish_requires_auth(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        # Make the delete request without the Authorization header
        resp = auth_client.delete(
            f"/api/v1/packages/{VALID_PKG['id']}/{VALID_PKG['version']}",
            headers={"Authorization": ""},
        )
        assert resp.status_code == 401

    def test_unpublish_unknown_returns_404(self, auth_client):
        resp = auth_client.delete("/api/v1/packages/simkjels/samples/sampledata/9.9.9")
        assert resp.status_code == 404

    def test_cannot_unpublish_others_package(self, client, auth_client):
        # testuser publishes
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        # other user tries to delete
        client.post(
            "/api/auth/register",
            json={"username": "otheruser", "password": "otherpass123"},
        )
        token = client.post(
            "/api/auth/token",
            json={"username": "otheruser", "password": "otherpass123"},
        ).json()["token"]
        resp = client.delete(
            f"/api/v1/packages/{VALID_PKG['id']}/{VALID_PKG['version']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
