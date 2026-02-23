"""Tests for /api/v1/packages, /api/v1/stats, /api/v1/publishers endpoints."""

from __future__ import annotations

VALID_PKG = {
    "id": "testuser/samples/sampledata",
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

    def test_wrong_publisher_returns_403(self, auth_client):
        resp = auth_client.post(
            "/api/v1/packages",
            json={**VALID_PKG, "id": "someone-else/samples/sampledata"},
        )
        assert resp.status_code == 403
        assert "publisher" in resp.json()["detail"].lower()


class TestGetPackage:
    def test_get_specific_version(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        resp = auth_client.get(
            f"/api/v1/packages/{VALID_PKG['id']}/{VALID_PKG['version']}"
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == VALID_PKG["id"]

    def test_get_unknown_returns_404(self, client):
        resp = client.get("/api/v1/packages/testuser/samples/sampledata/9.9.9")
        assert resp.status_code == 404

    def test_get_latest(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        auth_client.post("/api/v1/packages", json={**VALID_PKG, "version": "0.2.0"})
        resp = auth_client.get(f"/api/v1/packages/{VALID_PKG['id']}/latest")
        assert resp.status_code == 200
        assert resp.json()["version"] == "0.2.0"

    def test_get_latest_unknown_returns_404(self, client):
        resp = client.get("/api/v1/packages/testuser/samples/unknown/latest")
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
        resp = client.get("/api/v1/packages/testuser/samples/unknown")
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
        resp = auth_client.delete(
            f"/api/v1/packages/{VALID_PKG['id']}/{VALID_PKG['version']}",
            headers={"Authorization": ""},
        )
        assert resp.status_code == 401

    def test_unpublish_unknown_returns_404(self, auth_client):
        resp = auth_client.delete("/api/v1/packages/testuser/samples/sampledata/9.9.9")
        assert resp.status_code == 404

    def test_cannot_unpublish_others_package(self, client, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
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


# ---------------------------------------------------------------------------
# A2 — Stats endpoint
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_returns_zeros_on_empty_registry(self, client):
        resp = client.get("/api/v1/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["datasets"] == 0
        assert data["publishers"] == 0
        assert data["sources"] == 0

    def test_stats_counts_datasets(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        auth_client.post("/api/v1/packages", json={**VALID_PKG, "version": "0.2.0"})
        data = auth_client.get("/api/v1/stats").json()
        assert data["datasets"] == 2

    def test_stats_counts_publishers(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        data = auth_client.get("/api/v1/stats").json()
        assert data["publishers"] == 1

    def test_stats_counts_sources(self, auth_client):
        pkg_two_sources = {
            **VALID_PKG,
            "sources": [
                {"url": "https://example.com/a.csv", "format": "csv"},
                {"url": "https://example.com/b.csv", "format": "csv"},
            ],
        }
        auth_client.post("/api/v1/packages", json=pkg_two_sources)
        data = auth_client.get("/api/v1/stats").json()
        assert data["sources"] == 2

    def test_stats_aggregates_multiple_publishers(self, client):
        for username in ("alice", "bob"):
            client.post(
                "/api/auth/register",
                json={"username": username, "password": "password123"},
            )
            token = client.post(
                "/api/auth/token",
                json={"username": username, "password": "password123"},
            ).json()["token"]
            client.post(
                "/api/v1/packages",
                json={**VALID_PKG, "id": f"{username}/samples/sampledata"},
                headers={"Authorization": f"Bearer {token}"},
            )
        data = client.get("/api/v1/stats").json()
        assert data["publishers"] == 2
        assert data["datasets"] == 2


# ---------------------------------------------------------------------------
# A3 — Publisher endpoint
# ---------------------------------------------------------------------------


class TestPublisherEndpoint:
    def test_returns_publishers_packages(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        auth_client.post(
            "/api/v1/packages",
            json={**VALID_PKG, "id": "testuser/other/dataset", "version": "1.0.0"},
        )
        resp = auth_client.get("/api/v1/publishers/testuser")
        assert resp.status_code == 200
        data = resp.json()
        assert data["publisher"] == "testuser"
        assert data["package_count"] == 2
        assert len(data["packages"]) == 2

    def test_unknown_publisher_returns_404(self, client):
        resp = client.get("/api/v1/publishers/nobody")
        assert resp.status_code == 404

    def test_does_not_return_other_publishers_packages(self, client):
        for username in ("alice", "bob"):
            client.post(
                "/api/auth/register",
                json={"username": username, "password": "password123"},
            )
            token = client.post(
                "/api/auth/token",
                json={"username": username, "password": "password123"},
            ).json()["token"]
            client.post(
                "/api/v1/packages",
                json={**VALID_PKG, "id": f"{username}/samples/sampledata"},
                headers={"Authorization": f"Bearer {token}"},
            )
        data = client.get("/api/v1/publishers/alice").json()
        assert all(p["id"].startswith("alice/") for p in data["packages"])


# ---------------------------------------------------------------------------
# A4 — Namespace endpoint
# ---------------------------------------------------------------------------


class TestNamespaceEndpoint:
    def test_returns_namespace_packages(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        resp = auth_client.get("/api/v1/publishers/testuser/namespaces/samples")
        assert resp.status_code == 200
        data = resp.json()
        assert data["publisher"] == "testuser"
        assert data["namespace"] == "samples"
        assert len(data["packages"]) == 1

    def test_excludes_other_namespaces(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        auth_client.post(
            "/api/v1/packages",
            json={**VALID_PKG, "id": "testuser/other/dataset", "version": "1.0.0"},
        )
        data = auth_client.get(
            "/api/v1/publishers/testuser/namespaces/samples"
        ).json()
        assert all("testuser/samples/" in p["id"] for p in data["packages"])
        assert len(data["packages"]) == 1

    def test_unknown_namespace_returns_404(self, client):
        resp = client.get("/api/v1/publishers/testuser/namespaces/nosuchns")
        assert resp.status_code == 404

    def test_unknown_publisher_namespace_returns_404(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        resp = auth_client.get("/api/v1/publishers/nobody/namespaces/samples")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# A5 — Suggest endpoint
# ---------------------------------------------------------------------------


class TestSuggest:
    def test_returns_close_match(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        resp = auth_client.get("/api/v1/packages/suggest?q=testuser/samples/sampledtaa")
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "testuser/samples/sampledtaa"
        assert VALID_PKG["id"] in data["suggestions"]

    def test_empty_registry_returns_empty_list(self, client):
        resp = client.get("/api/v1/packages/suggest?q=anything")
        assert resp.status_code == 200
        assert resp.json()["suggestions"] == []

    def test_n_parameter_limits_results(self, auth_client):
        for i in range(5):
            auth_client.post(
                "/api/v1/packages",
                json={**VALID_PKG, "id": f"testuser/samples/data{i}", "version": "1.0.0"},
            )
        resp = auth_client.get("/api/v1/packages/suggest?q=testuser/samples/dat&n=2")
        assert resp.status_code == 200
        assert len(resp.json()["suggestions"]) <= 2

    def test_missing_q_returns_422(self, client):
        resp = client.get("/api/v1/packages/suggest")
        assert resp.status_code == 422

    def test_query_reflected_in_response(self, client):
        resp = client.get("/api/v1/packages/suggest?q=myquery")
        assert resp.json()["query"] == "myquery"


# ---------------------------------------------------------------------------
# A6 — Tag filter
# ---------------------------------------------------------------------------


class TestTagFilter:
    def test_filter_by_tag_returns_match(self, auth_client):
        tagged_pkg = {**VALID_PKG, "tags": ["climate", "weather"]}
        auth_client.post("/api/v1/packages", json=tagged_pkg)
        resp = auth_client.get("/api/v1/packages?tag=climate")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_filter_excludes_non_matching_tag(self, auth_client):
        auth_client.post("/api/v1/packages", json={**VALID_PKG, "tags": ["economics"]})
        resp = auth_client.get("/api/v1/packages?tag=climate")
        assert resp.json()["total"] == 0

    def test_empty_tag_returns_all(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        resp = auth_client.get("/api/v1/packages?tag=")
        assert resp.json()["total"] == 1

    def test_tag_filter_is_case_insensitive(self, auth_client):
        auth_client.post("/api/v1/packages", json={**VALID_PKG, "tags": ["Climate"]})
        resp = auth_client.get("/api/v1/packages?tag=climate")
        assert resp.json()["total"] == 1

    def test_q_and_tag_combined(self, auth_client):
        auth_client.post(
            "/api/v1/packages",
            json={**VALID_PKG, "title": "Oslo Weather", "tags": ["weather"]},
        )
        auth_client.post(
            "/api/v1/packages",
            json={
                **VALID_PKG,
                "id": "testuser/samples/other",
                "version": "1.0.0",
                "title": "Oslo Traffic",
                "tags": ["transport"],
            },
        )
        # Both match q=oslo, but only one has tag=weather
        resp = auth_client.get("/api/v1/packages?q=Oslo&tag=weather")
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["tags"] == ["weather"]


# ---------------------------------------------------------------------------
# A7 — FTS5 search
# ---------------------------------------------------------------------------


class TestFTS5Search:
    def test_search_finds_title_match(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        resp = auth_client.get("/api/v1/packages?q=Sample")
        assert resp.json()["total"] == 1

    def test_search_finds_publisher_name(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        # VALID_PKG publisher.name is "Simen Kjelsrud"
        resp = auth_client.get("/api/v1/packages?q=Kjelsrud")
        assert resp.json()["total"] == 1

    def test_search_finds_package_id(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        resp = auth_client.get("/api/v1/packages?q=sampledata")
        assert resp.json()["total"] == 1

    def test_search_no_match_returns_empty(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        resp = auth_client.get("/api/v1/packages?q=zzznomatch")
        assert resp.json()["total"] == 0

    def test_unpublished_package_not_in_search(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        auth_client.delete(
            f"/api/v1/packages/{VALID_PKG['id']}/{VALID_PKG['version']}"
        )
        resp = auth_client.get("/api/v1/packages?q=Sample")
        assert resp.json()["total"] == 0

    def test_force_overwrite_updates_fts_index(self, auth_client):
        # Use a distinctive title whose tokens don't appear in the package_id
        base_pkg = {**VALID_PKG, "title": "Unique Rainfall Measurements"}
        auth_client.post("/api/v1/packages", json=base_pkg)
        # Overwrite with a completely different title
        updated = {**VALID_PKG, "title": "Completely Different Title"}
        auth_client.post("/api/v1/packages?force=true", json=updated)
        # Old title tokens ("Rainfall") are gone from FTS index
        resp_old = auth_client.get("/api/v1/packages?q=Rainfall")
        assert resp_old.json()["total"] == 0
        # New title matches
        resp_new = auth_client.get("/api/v1/packages?q=Completely+Different")
        assert resp_new.json()["total"] == 1
