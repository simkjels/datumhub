"""Token-based authentication dependency."""

from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from datumhub.database import get_db

bearer = HTTPBearer(auto_error=False)


def generate_token() -> str:
    return secrets.token_hex(32)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    db = get_db()
    row = db.execute(
        """
        SELECT u.id, u.username
        FROM api_tokens t
        JOIN users u ON u.id = t.user_id
        WHERE t.token = ?
          AND (t.expires_at IS NULL OR t.expires_at > datetime('now'))
        """,
        (credentials.credentials,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return dict(row)
