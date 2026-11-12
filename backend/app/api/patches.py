"""Read-only patch API (M1). Stats/verdicts arrive in M2."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db

router = APIRouter(prefix="/patches", tags=["patches"])


@router.get("", response_model=list[schemas.PatchListOut])
def list_patches(db: Session = Depends(get_db)) -> list[schemas.PatchListOut]:
    rows = (
        db.query(
            models.Patch.id,
            models.Patch.title,
            models.Patch.patch_date,
            models.Patch.status,
            models.Patch.summary,
            func.count(models.Change.id).label("change_count"),
        )
        .outerjoin(models.Change)
        .group_by(models.Patch.id)
        .order_by(models.Patch.patch_date.desc().nullslast())
        .all()
    )
    return [schemas.PatchListOut(**dict(r._mapping)) for r in rows]


@router.get("/{patch_id}", response_model=schemas.PatchDetailOut)
def get_patch(patch_id: int, db: Session = Depends(get_db)) -> models.Patch:
    patch = db.get(models.Patch, patch_id)
    if patch is None:
        raise HTTPException(status_code=404, detail="Patch not found")
    return patch
