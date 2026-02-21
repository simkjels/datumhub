"""Auth routes: register and get token."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from datumhub.auth import generate_token
from datumhub.database import get_db
from datumhub.models import RegisterIn, TokenIn, TokenOut
from datumhub.password import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn) -> dict:
    """Create a new user account."""
    db = get_db()
    existing = db.execute(
        "SELECT id FROM users WHERE username = ?", (body.username,)
    ).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

    pw_hash = hash_password(body.password)
    db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (body.username, pw_hash),
    )
    db.commit()
    return {"registered": True, "username": body.username}


@router.post("/token", response_model=TokenOut)
def get_token(body: TokenIn) -> TokenOut:
    """Exchange credentials for an API token."""
    db = get_db()
    row = db.execute(
        "SELECT id, password_hash FROM users WHERE username = ?", (body.username,)
    ).fetchone()
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = generate_token()
    db.execute(
        "INSERT INTO api_tokens (user_id, token) VALUES (?, ?)",
        (row["id"], token),
    )
    db.commit()
    return TokenOut(token=token)
