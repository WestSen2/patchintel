"""PatchIntel API — entry point.

M1 scope: health check + patch history (read-only).
See docs/blueprint.md for the full architecture.
"""

from fastapi import FastAPI

app = FastAPI(
    title="PatchIntel",
    description="Deadlock patch-impact analytics: did the patch actually work?",
    version="0.1.0",
)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "service": "patchintel", "version": "0.1.0"}


# M1 routers land here:
#   /api/patches        — patch history + structured changes
#   /api/patches/{id}   — single patch with LLM summary
# M2: /api/heroes, /api/items, /api/builds, verdicts
# M3: /api/me/* (Steam OpenID, personal analytics)
