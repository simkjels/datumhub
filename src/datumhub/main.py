"""DatumHub API — FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from datumhub import __version__
from datumhub.database import init_db
from datumhub.routes import auth, packages


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="DatumHub API",
    description="Registry API for DatumHub — open datasets, open source.",
    version=__version__,
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(packages.router)


@app.get("/", tags=["meta"])
def root() -> dict:
    return {"name": "DatumHub API", "version": __version__, "docs": "/docs"}


def run() -> None:
    import uvicorn
    uvicorn.run("datumhub.main:app", host="0.0.0.0", port=8000, reload=True)
