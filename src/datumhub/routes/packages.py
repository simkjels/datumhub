"""Package routes: list, get, publish, unpublish, suggest."""

from __future__ import annotations

import difflib
import json
import re
import sqlite3
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from datumhub.auth import get_current_user
from datumhub.database import get_db
from datumhub.models import (
    PackageIn,
    PackageList,
    PackageOut,
    PackageVersionList,
    SuggestResponse,
)

router = APIRouter(prefix="/api/v1/packages", tags=["packages"])


def _row_to_out(row) -> PackageOut:
    data = json.loads(row["data"])
    return PackageOut(**data, published_at=row["published_at"], owner=row["owner"])


def _fts_query(q: str) -> str:
    """Convert a user query into a safe FTS5 MATCH expression.

    Each word gets prefix-match treatment ("word"*) joined with OR so that
    partial and multi-word queries work naturally.
    """
    clean = re.sub(r'[^\w\s]', ' ', q).strip()
    terms = [t for t in clean.split() if t]
    if not terms:
        return '""'
    return " OR ".join(f'"{t}"*' for t in terms)


# ---------------------------------------------------------------------------
# Read endpoints (public)
# ---------------------------------------------------------------------------


@router.get("/suggest", response_model=SuggestResponse)
def suggest_packages(
    q: str = Query(..., min_length=1, description="Partial package ID to match"),
    n: int = Query(5, ge=1, le=20, description="Maximum number of suggestions"),
) -> SuggestResponse:
    """Return up to n package IDs that closely match q."""
    db = get_db()
    all_ids: List[str] = [
        row[0]
        for row in db.execute(
            "SELECT DISTINCT package_id FROM packages"
        ).fetchall()
    ]
    matches = difflib.get_close_matches(q, all_ids, n=n, cutoff=0.4)
    return SuggestResponse(query=q, suggestions=matches)


@router.get("", response_model=PackageList)
def list_packages(
    q: Optional[str] = Query(None, description="Full-text search query"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> PackageList:
    """List or search all published packages."""
    db = get_db()

    # Build query parts dynamically
    joins: List[str] = ["JOIN users u ON u.id = p.owner_id"]
    conditions: List[str] = []
    params: List = []
    order_by = "p.published_at DESC"

    # Full-text search via FTS5 with LIKE fallback
    if q:
        try:
            fts_expr = _fts_query(q)
            joins.append("JOIN packages_fts ON packages_fts.rowid = p.id")
            conditions.append("packages_fts MATCH ?")
            params.append(fts_expr)
            order_by = "packages_fts.rank"
            # Smoke-test the FTS expression at query-build time by preparing it
            db.execute(
                "SELECT COUNT(*) FROM packages_fts WHERE packages_fts MATCH ?",
                (fts_expr,),
            )
        except sqlite3.OperationalError:
            # FTS5 unavailable or bad expression — fall back to LIKE
            joins = ["JOIN users u ON u.id = p.owner_id"]
            conditions = ["lower(p.data) LIKE ?"]
            params = [f"%{q.lower()}%"]
            order_by = "p.published_at DESC"

    # Tag filter (LIKE match on JSON array in data column)
    if tag:
        conditions.append("lower(p.data) LIKE ?")
        params.append(f'%"{tag.lower()}"%')

    joins_sql = " ".join(joins)
    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = db.execute(
        f"SELECT p.data, p.published_at, u.username AS owner"
        f" FROM packages p {joins_sql} {where_sql}"
        f" ORDER BY {order_by} LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()

    total = db.execute(
        f"SELECT COUNT(*) FROM packages p {joins_sql} {where_sql}",
        params,
    ).fetchone()[0]

    return PackageList(
        items=[_row_to_out(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_prev=offset > 0,
    )


@router.get("/{publisher}/{namespace}/{dataset}", response_model=PackageVersionList)
def get_all_versions(publisher: str, namespace: str, dataset: str) -> PackageVersionList:
    """Return all published versions of a package, newest first."""
    package_id = f"{publisher}/{namespace}/{dataset}"
    db = get_db()
    rows = db.execute(
        """
        SELECT p.data, p.published_at, u.username AS owner
        FROM packages p
        JOIN users u ON u.id = p.owner_id
        WHERE p.package_id = ?
        ORDER BY p.published_at DESC, p.id DESC
        """,
        (package_id,),
    ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail=f"Package {package_id!r} not found")
    versions = [_row_to_out(r) for r in rows]
    return PackageVersionList(id=package_id, versions=versions, total=len(versions))


@router.get("/{publisher}/{namespace}/{dataset}/latest", response_model=PackageOut)
def get_latest(publisher: str, namespace: str, dataset: str) -> PackageOut:
    """Return the most recently published version of a package."""
    package_id = f"{publisher}/{namespace}/{dataset}"
    db = get_db()
    row = db.execute(
        """
        SELECT p.data, p.published_at, u.username AS owner
        FROM packages p
        JOIN users u ON u.id = p.owner_id
        WHERE p.package_id = ?
        ORDER BY p.published_at DESC, p.id DESC
        LIMIT 1
        """,
        (package_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Package {package_id!r} not found")
    return _row_to_out(row)


@router.get("/{publisher}/{namespace}/{dataset}/{version}", response_model=PackageOut)
def get_package(publisher: str, namespace: str, dataset: str, version: str) -> PackageOut:
    """Return a specific version of a package."""
    package_id = f"{publisher}/{namespace}/{dataset}"
    db = get_db()
    row = db.execute(
        """
        SELECT p.data, p.published_at, u.username AS owner
        FROM packages p
        JOIN users u ON u.id = p.owner_id
        WHERE p.package_id = ? AND p.version = ?
        """,
        (package_id, version),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"Package {package_id}:{version} not found"
        )
    return _row_to_out(row)


# ---------------------------------------------------------------------------
# Write endpoints (authenticated)
# ---------------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PackageOut)
def publish_package(
    body: PackageIn,
    force: bool = Query(False, description="Overwrite an existing version"),
    user: dict = Depends(get_current_user),
) -> PackageOut:
    """Publish a new dataset (or overwrite with ?force=true)."""
    publisher, _, _ = body.id.split("/")
    if publisher != user["username"]:
        raise HTTPException(
            status_code=403,
            detail=f"Publisher slug '{publisher}' does not match your username '{user['username']}'.",
        )

    db = get_db()
    existing = db.execute(
        "SELECT owner_id FROM packages WHERE package_id = ? AND version = ?",
        (body.id, body.version),
    ).fetchone()

    if existing:
        if not force:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{body.id}:{body.version} already published. "
                    "Use ?force=true to overwrite."
                ),
            )
        if existing["owner_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="You do not own this package")
        db.execute(
            "DELETE FROM packages WHERE package_id = ? AND version = ?",
            (body.id, body.version),
        )

    db.execute(
        "INSERT INTO packages (package_id, version, owner_id, data) VALUES (?, ?, ?, ?)",
        (body.id, body.version, user["id"], body.model_dump_json()),
    )
    db.commit()
    publisher, namespace, dataset = body.id.split("/")
    return get_package(publisher, namespace, dataset, body.version)


@router.delete("/{publisher}/{namespace}/{dataset}/{version}")
def unpublish_package(
    publisher: str,
    namespace: str,
    dataset: str,
    version: str,
    user: dict = Depends(get_current_user),
) -> Response:
    """Remove a published package version."""
    package_id = f"{publisher}/{namespace}/{dataset}"
    db = get_db()
    row = db.execute(
        "SELECT owner_id FROM packages WHERE package_id = ? AND version = ?",
        (package_id, version),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{package_id}:{version} not found")
    if row["owner_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="You do not own this package")

    db.execute(
        "DELETE FROM packages WHERE package_id = ? AND version = ?",
        (package_id, version),
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
