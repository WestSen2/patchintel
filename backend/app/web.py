"""Server-rendered UI (M1 decision D1).

Minimal Jinja2 pages over the same data the JSON API serves. React replaces
this in M2 when charts/filtering arrive; the API is unaffected.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    rows = (
        db.query(models.Patch, func.count(models.Change.id).label("change_count"))
        .outerjoin(models.Change)
        .group_by(models.Patch.id)
        .order_by(models.Patch.patch_date.desc().nullslast())
        .all()
    )
    return templates.TemplateResponse(
        "patches.html", {"request": request, "rows": rows}
    )


@router.get("/patches/{patch_id}", response_class=HTMLResponse)
def patch_detail(patch_id: int, request: Request, db: Session = Depends(get_db)):
    patch = db.get(models.Patch, patch_id)
    if patch is None:
        raise HTTPException(status_code=404, detail="Patch not found")
    return templates.TemplateResponse(
        "patch_detail.html", {"request": request, "patch": patch}
    )
