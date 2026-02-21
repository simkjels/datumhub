"""Pydantic request/response models for the DatumHub API."""

from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel, field_validator

# Must match the CLI's ID_PATTERN: publisher/namespace/dataset
# Publisher allows dots for domain-based publishers (e.g. norge.no)
_SLUG = r"[a-z0-9]([a-z0-9-]*[a-z0-9])?"
_PUBLISHER = r"[a-z0-9]([a-z0-9.-]*[a-z0-9])?"
ID_PATTERN = re.compile(rf"^{_PUBLISHER}/{_SLUG}/{_SLUG}$")
CHECKSUM_PATTERN = re.compile(r"^[a-z0-9]+:[a-f0-9]+$")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class RegisterIn(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9_-]{1,29}$", v):
            raise ValueError(
                "Username must be 2–30 lowercase letters, digits, hyphens, or underscores"
            )
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class TokenIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    token: str


# ---------------------------------------------------------------------------
# Packages
# ---------------------------------------------------------------------------


class SourceModel(BaseModel):
    url: str
    format: str
    size: Optional[int] = None
    checksum: Optional[str] = None

    @field_validator("checksum")
    @classmethod
    def validate_checksum(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not CHECKSUM_PATTERN.match(v):
            raise ValueError("checksum must be in the form 'algorithm:hexdigest'")
        return v


class PublisherModel(BaseModel):
    name: str
    url: Optional[str] = None


class PackageIn(BaseModel):
    id: str
    version: str
    title: str
    description: Optional[str] = None
    license: Optional[str] = None
    publisher: PublisherModel
    tags: List[str] = []
    sources: List[SourceModel]

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError(
                f"Invalid package id {v!r}. "
                "Expected publisher/namespace/dataset "
                "(slash-separated, publisher may contain dots, e.g. norge.no/population/census)."
            )
        return v

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, v: List[SourceModel]) -> List[SourceModel]:
        if not v:
            raise ValueError("sources must not be empty")
        return v


class PackageOut(PackageIn):
    published_at: str
    owner: str


class PackageList(BaseModel):
    items: List[PackageOut]
    total: int
    limit: int
    offset: int
