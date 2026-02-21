"""Tests for the HTML catalog web frontend."""

from __future__ import annotations

VALID_PKG = {
    "id": "simkjels/samples/sampledata",
    "version": "0.1.0",
    "title": "Sample Data",
    "publisher": {"name": "Simen Kjelsrud"},
    "sources": [{"url": "https://example.com/sample.csv", "format": "csv"}],
}


class TestCatalogIndex:
    def test_returns_200(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_returns_html(self, client):
        r = client.get("/")
        assert "text/html" in r.headers["content-type"]

    def test_contains_branding(self, client):
        r = client.get("/")
        assert "DatumHub" in r.text

    def test_shows_dataset_count(self, client):
        r = client.get("/")
        assert "0 datasets" in r.text

    def test_shows_published_package(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        r = auth_client.get("/")
        assert r.status_code == 200
        assert "Sample Data" in r.text
        assert "simkjels/samples/sampledata" in r.text

    def test_count_reflects_published(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        r = auth_client.get("/")
        assert "1 dataset" in r.text

    def test_search_returns_match(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        r = auth_client.get("/?q=sample")
        assert r.status_code == 200
        assert "Sample Data" in r.text

    def test_search_returns_no_match(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        r = auth_client.get("/?q=zzznomatch")
        assert r.status_code == 200
        assert "Sample Data" not in r.text
        assert "0 result" in r.text

    def test_card_links_to_dataset(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        r = auth_client.get("/")
        assert "/simkjels/samples/sampledata" in r.text


class TestCatalogDataset:
    def test_known_dataset_returns_200(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        r = auth_client.get("/simkjels/samples/sampledata")
        assert r.status_code == 200

    def test_shows_title(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        r = auth_client.get("/simkjels/samples/sampledata")
        assert "Sample Data" in r.text

    def test_shows_identifier(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        r = auth_client.get("/simkjels/samples/sampledata")
        assert "simkjels/samples/sampledata" in r.text

    def test_shows_source_url(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        r = auth_client.get("/simkjels/samples/sampledata")
        assert "https://example.com/sample.csv" in r.text

    def test_shows_pull_snippet(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        r = auth_client.get("/simkjels/samples/sampledata")
        assert "datum pull" in r.text

    def test_shows_size_when_present(self, auth_client):
        pkg = {**VALID_PKG, "sources": [
            {"url": "https://example.com/sample.csv", "format": "csv", "size": 2048}
        ]}
        auth_client.post("/api/v1/packages", json=pkg)
        r = auth_client.get("/simkjels/samples/sampledata")
        assert "2.0 KB" in r.text

    def test_shows_tags(self, auth_client):
        pkg = {**VALID_PKG, "tags": ["weather", "norway"]}
        auth_client.post("/api/v1/packages", json=pkg)
        r = auth_client.get("/simkjels/samples/sampledata")
        assert "weather" in r.text
        assert "norway" in r.text

    def test_unknown_dataset_returns_404(self, client):
        r = client.get("/nobody/nada/nothing")
        assert r.status_code == 404

    def test_404_shows_error_message(self, client):
        r = client.get("/nobody/nada/nothing")
        assert "nobody/nada/nothing" in r.text

    def test_version_history_shown_for_multiple_versions(self, auth_client):
        auth_client.post("/api/v1/packages", json=VALID_PKG)
        v2 = {**VALID_PKG, "version": "0.2.0"}
        auth_client.post("/api/v1/packages", json=v2)
        r = auth_client.get("/simkjels/samples/sampledata")
        assert "0.1.0" in r.text
        assert "0.2.0" in r.text
