"""Web catalog routes — HTML frontend for DatumHub."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from datumhub.database import get_db

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["catalog"], include_in_schema=False)


def _fmt_size(n: Optional[int]) -> str:
    if n is None:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _load_packages(q: str = "", limit: int = 200, offset: int = 0):
    db = get_db()
    if q:
        pattern = f"%{q.lower()}%"
        rows = db.execute(
            "SELECT p.data, p.published_at, u.username AS owner"
            " FROM packages p JOIN users u ON u.id = p.owner_id"
            " WHERE lower(p.data) LIKE ?"
            " ORDER BY p.published_at DESC LIMIT ? OFFSET ?",
            (pattern, limit, offset),
        ).fetchall()
        total = db.execute(
            "SELECT COUNT(*) FROM packages WHERE lower(data) LIKE ?", (pattern,)
        ).fetchone()[0]
    else:
        rows = db.execute(
            "SELECT p.data, p.published_at, u.username AS owner"
            " FROM packages p JOIN users u ON u.id = p.owner_id"
            " ORDER BY p.published_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        total = db.execute("SELECT COUNT(*) FROM packages").fetchone()[0]

    items = []
    for row in rows:
        pkg = json.loads(row["data"])
        pkg["published_at"] = row["published_at"]
        pkg["owner"] = row["owner"]
        items.append(pkg)
    return items, total


@router.get("/", response_class=HTMLResponse)
def catalog(request: Request, q: str = ""):
    items, total = _load_packages(q=q)
    return templates.TemplateResponse(
        request,
        "catalog.html",
        {"packages": items, "total": total, "q": q},
    )


@router.get("/{publisher}/{namespace}/{dataset}", response_class=HTMLResponse)
def dataset_detail(
    request: Request,
    publisher: str,
    namespace: str,
    dataset: str,
) -> HTMLResponse:
    db = get_db()
    package_id = f"{publisher}/{namespace}/{dataset}"

    rows = db.execute(
        "SELECT p.data, p.published_at, u.username AS owner"
        " FROM packages p JOIN users u ON u.id = p.owner_id"
        " WHERE p.package_id = ?"
        " ORDER BY p.published_at DESC",
        (package_id,),
    ).fetchall()

    if not rows:
        items, total = _load_packages()
        return templates.TemplateResponse(
            request,
            "catalog.html",
            {"packages": items, "total": total, "q": "", "not_found": package_id},
            status_code=404,
        )

    versions = []
    for row in rows:
        pkg = json.loads(row["data"])
        pkg["published_at"] = row["published_at"]
        pkg["owner"] = row["owner"]
        versions.append(pkg)

    latest = versions[0]
    return templates.TemplateResponse(
        request,
        "dataset.html",
        {"pkg": latest, "versions": versions, "fmt_size": _fmt_size},
    )
