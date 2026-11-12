"""M2 stats API: heroes, items, per-patch impact (verdicts), purchase curves."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import get_settings
from ..db import get_db
from ..upstream import deadlock_analytics

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


CURVE_TTL = timedelta(hours=24)


@router.get("/items/{item_id}/purchase-curve", response_model=list[schemas.PurchaseCurvePointOut])
def item_purchase_curve_endpoint(
    item_id: int,
    db: Session = Depends(get_db),
    settings=Depends(get_settings),
):
    """Minute-level win-rate-by-purchase-time curve (2-min slices, 0–50 min).

    Cached for 24h — building a curve costs ~25 upstream calls.
    """
    item = db.get(models.Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    rows = (
        db.query(models.ItemPurchaseCurve)
        .filter_by(item_id=item_id)
        .order_by(models.ItemPurchaseCurve.bucket_start_s)
        .all()
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    fresh = rows and all(now - r.captured_at < CURVE_TTL for r in rows)

    if not fresh:
        curve = deadlock_analytics.item_purchase_curve(settings, item_id)
        db.query(models.ItemPurchaseCurve).filter_by(item_id=item_id).delete()
        for point in curve:
            db.add(
                models.ItemPurchaseCurve(
                    item_id=item_id,
                    bucket_start_s=point["bucket_start_s"],
                    wins=point["wins"],
                    losses=point["losses"],
                    matches=point["matches"],
                    captured_at=now,
                )
            )
        db.commit()
        rows = (
            db.query(models.ItemPurchaseCurve)
            .filter_by(item_id=item_id)
            .order_by(models.ItemPurchaseCurve.bucket_start_s)
            .all()
        )

    return [
        schemas.PurchaseCurvePointOut(
            bucket_start_s=r.bucket_start_s,
            wins=r.wins,
            losses=r.losses,
            matches=r.matches,
            win_rate=round(r.wins / r.matches, 4) if r.matches else None,
        )
        for r in rows
    ]
