"""Shared test fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import datumhub.config as cfg
import datumhub.database as db_module
from datumhub.main import app

VALID_PKG = {
    "id": "simkjels.samples.sampledata",
    "version": "0.1.0",
    "title": "Sample Data",
    "publisher": {"name": "Simen Kjelsrud"},
    "sources": [{"url": "https://example.com/sample.csv", "format": "csv"}],
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Test client backed by a fresh temporary database."""
    monkeypatch.setattr(cfg, "DB_PATH", tmp_path / "test.db")
    # Reset any existing connection so lifespan picks up the new path
    if db_module._conn is not None:
        db_module._conn.close()
        db_module._conn = None
    with TestClient(app) as c:
        yield c
    if db_module._conn is not None:
        db_module._conn.close()
        db_module._conn = None


@pytest.fixture()
def auth_client(client):
    """A client that is already registered and authenticated."""
    client.post(
        "/api/auth/register",
        json={"username": "testuser", "password": "testpass123"},
    )
    resp = client.post(
        "/api/auth/token",
        json={"username": "testuser", "password": "testpass123"},
    )
    token = resp.json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
