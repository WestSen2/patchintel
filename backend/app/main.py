"""PatchIntel API — entry point.

M1: health + read-only patch API + server-rendered patch history UI.
M2 adds stats/verdicts; M3 adds Steam OpenID + personal analytics.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.patches import router as patches_router
from .db import init_db
from .web import router as web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # Alembic replaces create_all once the schema stabilizes (M2)
    yield


app = FastAPI(
    title="PatchIntel",
    description="Deadlock patch-impact analytics: did the patch actually work?",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(patches_router, prefix="/api")
app.include_router(web_router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "service": "patchintel", "version": "0.1.0"}
