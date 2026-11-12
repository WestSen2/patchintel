"""PatchIntel API — entry point.

M1: health + read-only patch API + server-rendered patch history UI.
M2 adds stats/verdicts; M3 adds Steam OpenID + personal analytics.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from .api.auth import router as auth_router
from .api.patches import router as patches_router
from .api.stats import router as stats_router
from .config import get_settings
from .db import init_db
from .web import router as web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # Alembic replaces create_all once the schema stabilizes
    yield


app = FastAPI(
    title="PatchIntel",
    description="Deadlock patch-impact analytics: did the patch actually work?",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=get_settings().app_secret_key,
    https_only=False,  # local dev; set behind TLS in production
    same_site="lax",
    max_age=30 * 24 * 3600,
)

app.include_router(patches_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(web_router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "service": "patchintel", "version": "0.2.0"}
