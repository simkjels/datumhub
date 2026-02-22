"""User profile routes."""

from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from datumhub.auth import get_current_user
from datumhub.database import get_db
from datumhub.models import PackageOut, UserProfile

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _packages_for_user(user_id: int) -> List[PackageOut]:
    db = get_db()
    rows = db.execute(
        """
        SELECT p.data, p.published_at, u.username AS owner
        FROM packages p
        JOIN users u ON u.id = p.owner_id
        WHERE p.owner_id = ?
        ORDER BY p.published_at DESC
        """,
        (user_id,),
    ).fetchall()
    result = []
    for row in rows:
        data = json.loads(row["data"])
        data["published_at"] = row["published_at"]
        data["owner"] = row["owner"]
        result.append(PackageOut(**data))
    return result


# /me must be registered before /{username} so it isn't captured as a username.

@router.get("/me", response_model=UserProfile)
def get_me(user: dict = Depends(get_current_user)) -> UserProfile:
    """Return the authenticated user's profile and their published packages."""
    db = get_db()
    row = db.execute(
        "SELECT id, username, created_at FROM users WHERE id = ?",
        (user["id"],),
    ).fetchone()
    packages = _packages_for_user(row["id"])
    return UserProfile(
        username=row["username"],
        joined_at=row["created_at"],
        package_count=len(packages),
        packages=packages,
    )


@router.get("/{username}", response_model=UserProfile)
def get_user(username: str) -> UserProfile:
    """Return a public user profile and their published packages."""
    db = get_db()
    row = db.execute(
        "SELECT id, username, created_at FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"User {username!r} not found")
    packages = _packages_for_user(row["id"])
    return UserProfile(
        username=row["username"],
        joined_at=row["created_at"],
        package_count=len(packages),
        packages=packages,
    )
