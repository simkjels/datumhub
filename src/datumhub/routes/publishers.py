"""Publisher, namespace, and site-stats routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from datumhub.database import get_db
from datumhub.models import NamespaceData, PackageOut, PublisherData, SiteStats

router = APIRouter(prefix="/api/v1", tags=["publishers"])


def _row_to_out(row) -> PackageOut:
    data = json.loads(row["data"])
    return PackageOut(**data, published_at=row["published_at"], owner=row["owner"])


# ---------------------------------------------------------------------------
# Site-wide stats
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=SiteStats)
def get_stats() -> SiteStats:
    """Aggregate counts for the catalog homepage."""
    db = get_db()

    total_datasets = db.execute("SELECT COUNT(*) FROM packages").fetchone()[0]

    publisher_count = db.execute(
        """
        SELECT COUNT(DISTINCT substr(package_id, 1, instr(package_id, '/') - 1))
        FROM packages
        """
    ).fetchone()[0]

    source_count = db.execute(
        """
        SELECT COALESCE(
            SUM(json_array_length(json_extract(data, '$.sources'))),
            0
        )
        FROM packages
        """
    ).fetchone()[0]

    return SiteStats(
        datasets=total_datasets,
        publishers=publisher_count,
        sources=source_count,
    )


# ---------------------------------------------------------------------------
# Publisher endpoints
# ---------------------------------------------------------------------------


@router.get("/publishers/{publisher}", response_model=PublisherData)
def get_publisher(publisher: str) -> PublisherData:
    """All dataset versions published under a publisher slug."""
    db = get_db()
    rows = db.execute(
        """
        SELECT p.data, p.published_at, u.username AS owner
        FROM packages p
        JOIN users u ON u.id = p.owner_id
        WHERE p.package_id LIKE ?
        ORDER BY p.published_at DESC
        """,
        (f"{publisher}/%",),
    ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail=f"Publisher '{publisher}' not found")

    packages = [_row_to_out(r) for r in rows]
    return PublisherData(
        publisher=publisher,
        package_count=len(packages),
        packages=packages,
    )


@router.get("/publishers/{publisher}/namespaces/{namespace}", response_model=NamespaceData)
def get_namespace(publisher: str, namespace: str) -> NamespaceData:
    """All dataset versions in a publisher/namespace."""
    db = get_db()
    rows = db.execute(
        """
        SELECT p.data, p.published_at, u.username AS owner
        FROM packages p
        JOIN users u ON u.id = p.owner_id
        WHERE p.package_id LIKE ?
        ORDER BY p.published_at DESC
        """,
        (f"{publisher}/{namespace}/%",),
    ).fetchall()
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Namespace '{publisher}/{namespace}' not found",
        )

    packages = [_row_to_out(r) for r in rows]
    return NamespaceData(
        publisher=publisher,
        namespace=namespace,
        packages=packages,
    )
