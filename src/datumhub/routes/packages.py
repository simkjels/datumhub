"""Package routes: list, get, publish, unpublish."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from datumhub.auth import get_current_user
from datumhub.database import get_db
from datumhub.models import PackageIn, PackageList, PackageOut

router = APIRouter(prefix="/api/v1/packages", tags=["packages"])


def _row_to_out(row) -> PackageOut:
    data = json.loads(row["data"])
    return PackageOut(**data, published_at=row["published_at"], owner=row["owner"])


# ---------------------------------------------------------------------------
# Read endpoints (public)
# ---------------------------------------------------------------------------


@router.get("", response_model=PackageList)
def list_packages(
    q: Optional[str] = Query(None, description="Full-text search query"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PackageList:
    """List or search all published packages."""
    db = get_db()
    base_join = """
        FROM packages p
        JOIN users u ON u.id = p.owner_id
    """
    if q:
        pattern = f"%{q.lower()}%"
        rows = db.execute(
            f"SELECT p.data, p.published_at, u.username AS owner {base_join}"
            " WHERE lower(p.data) LIKE ?"
            " ORDER BY p.published_at DESC LIMIT ? OFFSET ?",
            (pattern, limit, offset),
        ).fetchall()
        total = db.execute(
            "SELECT COUNT(*) FROM packages WHERE lower(data) LIKE ?", (pattern,)
        ).fetchone()[0]
    else:
        rows = db.execute(
            f"SELECT p.data, p.published_at, u.username AS owner {base_join}"
            " ORDER BY p.published_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        total = db.execute("SELECT COUNT(*) FROM packages").fetchone()[0]

    return PackageList(
        items=[_row_to_out(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


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
