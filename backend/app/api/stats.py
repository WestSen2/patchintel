"""M2 stats API: heroes, items, and per-patch impact (verdicts)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db

router = APIRouter(tags=["stats"])


@router.get("/patches/{patch_id}/impact", response_model=schemas.PatchImpactOut)
def patch_impact(patch_id: int, db: Session = Depends(get_db)):
    patch = db.get(models.Patch, patch_id)
    if patch is None:
        raise HTTPException(status_code=404, detail="Patch not found")
    return schemas.PatchImpactOut(
        patch_id=patch.id,
        title=patch.title,
        patch_date=patch.patch_date,
        verdicts=[schemas.VerdictOut.model_validate(v) for v in patch.verdicts],
    )


@router.get("/heroes", response_model=list[schemas.HeroOut])
def list_heroes(db: Session = Depends(get_db)):
    return db.query(models.Hero).order_by(models.Hero.name).all()


@router.get("/heroes/{hero_id}", response_model=schemas.HeroDetailOut)
def hero_detail(hero_id: int, db: Session = Depends(get_db)):
    hero = db.get(models.Hero, hero_id)
    if hero is None:
        raise HTTPException(status_code=404, detail="Hero not found")
    snapshots = (
        db.query(models.StatSnapshot)
        .filter_by(entity_type="hero", entity_id=hero_id)
        .order_by(models.StatSnapshot.window_start)
        .all()
    )
    changes = (
        db.query(models.Change)
        .filter_by(entity_type="hero", entity_id=hero_id)
        .order_by(models.Change.id)
        .all()
    )
    return schemas.HeroDetailOut(
        id=hero.id,
        name=hero.name,
        snapshots=[schemas.SnapshotOut.model_validate(s) for s in snapshots],
        changes=[schemas.ChangeOut.model_validate(c) for c in changes],
    )


@router.get("/items", response_model=list[schemas.ItemOut])
def list_items(db: Session = Depends(get_db)):
    return db.query(models.Item).order_by(models.Item.name).all()


@router.get("/items/{item_id}", response_model=schemas.ItemDetailOut)
def item_detail(item_id: int, db: Session = Depends(get_db)):
    item = db.get(models.Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    snapshots = (
        db.query(models.StatSnapshot)
        .filter_by(entity_type="item", entity_id=item_id)
        .order_by(models.StatSnapshot.window_start)
        .all()
    )
    changes = (
        db.query(models.Change)
        .filter_by(entity_type="item", entity_id=item_id)
        .order_by(models.Change.id)
        .all()
    )
    timing = (
        db.query(models.ItemTimingSnapshot)
        .filter_by(item_id=item_id)
        .order_by(models.ItemTimingSnapshot.captured_at)
        .all()
    )
    return schemas.ItemDetailOut(
        id=item.id,
        name=item.name,
        tier=item.tier,
        cost=item.cost,
        snapshots=[schemas.SnapshotOut.model_validate(s) for s in snapshots],
        changes=[schemas.ChangeOut.model_validate(c) for c in changes],
        timing=[schemas.TimingOut.model_validate(t) for t in timing],
    )
