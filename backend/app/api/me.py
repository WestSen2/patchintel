"""M3 personal endpoints — all require a signed-in user (session cookie)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import Settings, get_settings
from ..db import get_db
from ..personal import analytics, sync
from .auth import get_current_user

router = APIRouter(tags=["me"])

SYNC_COOLDOWN = timedelta(minutes=2)


@router.post("/me/sync")
def sync_matches(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: models.User = Depends(get_current_user),
):
    if user.last_sync_at and datetime.now(timezone.utc).replace(
        tzinfo=None
    ) - user.last_sync_at < SYNC_COOLDOWN:
        raise HTTPException(
            status_code=429,
            detail=f"Synced recently — wait {SYNC_COOLDOWN.seconds // 60} min between syncs",
        )
    return sync.sync_user(db, settings, user)


@router.get("/me/matches", response_model=list[schemas.UserMatchOut])
def my_matches(
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.UserMatch)
        .filter_by(user_id=user.id)
        .order_by(models.UserMatch.played_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/me/sessions", response_model=list[schemas.SessionOut])
def my_sessions(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.PlaySession)
        .filter_by(user_id=user.id)
        .order_by(models.PlaySession.started_at.desc())
        .all()
    )


@router.get("/me/analytics", response_model=schemas.MyAnalyticsOut)
def my_analytics(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    matches = (
        db.query(models.UserMatch)
        .filter_by(user_id=user.id)
        .order_by(models.UserMatch.played_at)
        .all()
    )
    hero_names = {h.id: h.name for h in db.query(models.Hero).all()}
    return analytics.compute_analytics(matches, user.timezone, hero_names=hero_names)


@router.get("/me/patch-impact")
def my_patch_impact(
    limit: int = Query(default=3, le=10),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Recent patches that touched the user's top-5 heroes, with verdicts."""
    matches = db.query(models.UserMatch).filter_by(user_id=user.id).all()
    hero_ids = {h["hero_id"] for h in analytics.top_heroes(matches)}
    if not hero_ids:
        return {"hero_ids": [], "patches": []}

    verdicts = (
        db.query(models.Verdict)
        .filter(
            models.Verdict.entity_type == "hero",
            models.Verdict.entity_id.in_(hero_ids),
        )
        .all()
    )
    by_patch: dict[int, list[models.Verdict]] = {}
    for v in verdicts:
        by_patch.setdefault(v.patch_id, []).append(v)

    patches = (
        db.query(models.Patch)
        .filter(models.Patch.id.in_(by_patch.keys()))
        .order_by(models.Patch.patch_date.desc())
        .limit(limit)
        .all()
    )
    return {
        "hero_ids": sorted(hero_ids),
        "patches": [
            {
                "patch_id": p.id,
                "title": p.title,
                "patch_date": p.patch_date,
                "verdicts": [
                    schemas.VerdictOut.model_validate(v).model_dump(mode="json")
                    for v in by_patch.get(p.id, [])
                ],
            }
            for p in patches
        ],
    }
