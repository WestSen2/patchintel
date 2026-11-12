"""Seed a fresh database with realistic DEMO data — no API keys needed.

    python scripts/seed_demo.py

Creates 3 demo patches with extracted changes, pre/post snapshots, verdicts,
and item timing buckets so the whole site (M1–M2 views) is browsable
immediately. Idempotent: skips if demo patches already exist.

Demo data is clearly labeled ("[DEMO]" in summaries). It exists so reviewers
and deploys work without upstream APIs — never present it as real data.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import models
from app.db import SessionLocal, init_db

DEMO_TAG = "demo"


def _patch(db, gid, title, days_ago, changes):
    existing = db.query(models.Patch).filter_by(steam_gid=gid).one_or_none()
    if existing:
        return None
    date = datetime(2026, 11, 12) - timedelta(days=days_ago)
    patch = models.Patch(
        steam_gid=gid,
        title=title,
        patch_date=date,
        source_url=f"https://example.com/{gid}",
        raw_text="\n".join(c[3] for c in changes),
        status="extracted",
        summary=f"[DEMO] {title} — fabricated data for demonstration.",
        llm_generated=False,
    )
    for entity_type, entity_name, entity_id, source_line, change_type in changes:
        patch.changes.append(
            models.Change(
                entity_type=entity_type,
                entity_name=entity_name,
                entity_id=entity_id,
                change_type=change_type,
                description=source_line,
                numbers=[],
                source_line=source_line,
            )
        )
    db.add(patch)
    db.commit()
    return patch


def _snap(db, patch, entity_type, entity_id, pre_wr, post_wr, matches, pick):
    date = patch.patch_date
    for window, wr, start, end in (
        ("pre", pre_wr, date - timedelta(days=7), date),
        ("post", post_wr, date + timedelta(days=1), date + timedelta(days=8)),
    ):
        wins = round(matches * wr)
        db.add(
            models.StatSnapshot(
                entity_type=entity_type,
                entity_id=entity_id,
                patch_id=patch.id,
                window=window,
                window_start=start,
                window_end=end,
                truncated=False,
                win_rate=wr,
                pick_rate=pick,
                matches=matches,
                extra={"wins": wins},
            )
        )


def _verdict(db, patch, change, pre_wr, post_wr, matches, verdict, reason, direction):
    db.add(
        models.Verdict(
            patch_id=patch.id,
            change_id=change.id,
            entity_type=change.entity_type,
            entity_id=change.entity_id or 0,
            expected_direction=direction,
            pre_win_rate=pre_wr,
            post_win_rate=post_wr,
            delta_win_rate=round(post_wr - pre_wr, 4),
            pre_matches=matches,
            post_matches=matches,
            ci_half_width=0.012,
            verdict=verdict,
            reason=reason,
        )
    )


def _timing(db, patch, item_id, avg_s, early, mid, late, matches):
    for window in ("pre", "post"):
        db.add(
            models.ItemTimingSnapshot(
                item_id=item_id,
                patch_id=patch.id,
                window=window,
                avg_buy_time_s=avg_s,
                avg_buy_time_relative=avg_s / 40,
                win_rate_early=early,
                win_rate_mid=mid,
                win_rate_late=late,
                matches=matches,
            )
        )


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        heroes = db.query(models.Hero).limit(6).all()
        items = db.query(models.Item).limit(4).all()
        if not heroes or not items:
            print("[demo] no heroes/items seeded — fabricating standalone rows")
            if not heroes:
                for i, name in enumerate(
                    ["Abrams", "Infernus", "Ivy", "Kelvin", "Lash", "Warden"], start=1
                ):
                    db.add(models.Hero(id=i, name=name))
            if not items:
                for i, (name, tier, cost) in enumerate(
                    [("Headhunter", 3, 3500), ("Lifesteal", 2, 1600),
                     ("Colossus", 4, 6200), ("Fleetfoot", 1, 500)], start=1
                ):
                    db.add(models.Item(id=i, name=name, tier=tier, cost=cost))
            db.commit()
            heroes = db.query(models.Hero).limit(6).all()
            items = db.query(models.Item).limit(4).all()

        h = {x.name: x for x in heroes}
        it = {x.name: x for x in items}
        hero_list = list(h.values())
        item_list = list(it.values())

        # Patch 1: big gameplay update — mix of worked/backfired/unclear
        changes1 = [
            ("hero", hero_list[0].name, hero_list[0].id,
             f"{hero_list[0].name}: Base damage reduced from 30 to 27", "nerf"),
            ("hero", hero_list[1].name, hero_list[1].id,
             f"{hero_list[1].name}: Ability cooldown reduced from 12s to 9s", "buff"),
            ("hero", hero_list[2].name, hero_list[2].id,
             f"{hero_list[2].name}: Movement speed increased by 0.3", "buff"),
            ("item", item_list[0].name, item_list[0].id,
             f"{item_list[0].name}: Cost increased from 3200 to 3500", "nerf"),
        ]
        p1 = _patch(db, f"{DEMO_TAG}-1", "Gameplay Update — Demo Alpha", 21, changes1)

        changes2 = [
            ("hero", hero_list[3].name, hero_list[3].id,
             f"{hero_list[3].name}: Health regen reduced from 2.5 to 1.5", "nerf"),
            ("hero", hero_list[4].name, hero_list[4].id,
             f"{hero_list[4].name}: Ultimate damage increased by 15%", "buff"),
        ]
        p2 = _patch(db, f"{DEMO_TAG}-2", "Gameplay Update — Demo Beta", 12, changes2)

        changes3 = [
            ("hero", hero_list[5].name, hero_list[5].id,
             f"{hero_list[5].name}: Fixed ability interaction with slow effects", "bugfix"),
        ]
        p3 = _patch(db, f"{DEMO_TAG}-3", "Minor Update — Demo Gamma", 4, changes3)

        made = [p for p in (p1, p2, p3) if p is not None]
        if not made:
            print("[demo] demo patches already present — nothing to do")
            return

        if p1:
            _snap(db, p1, "hero", hero_list[0].id, 0.524, 0.491, 12000, 0.18)
            _snap(db, p1, "hero", hero_list[1].id, 0.478, 0.512, 9000, 0.12)
            _snap(db, p1, "hero", hero_list[2].id, 0.501, 0.480, 300, 0.05)  # low sample
            _snap(db, p1, "item", item_list[0].id, 0.515, 0.502, 20000, 0.22)
            _verdict(db, p1, p1.changes[0], 0.524, 0.491, 12000, "worked",
                     "Win rate dropped 3.3 points beyond the 95% CI after the damage nerf.", "down")
            _verdict(db, p1, p1.changes[1], 0.478, 0.512, 9000, "backfired",
                     "Cooldown buff overshot — win rate rose 3.4 points beyond the CI.", "up")
            _verdict(db, p1, p1.changes[2], 0.478, 0.480, 300, "insufficient_data",
                     "Only 300 matches per window — under the 500-match floor.", "up")
            _verdict(db, p1, p1.changes[3], 0.515, 0.502, 20000, "unclear",
                     "Delta within the confidence interval; cost increase may need more time.", "down")
            _timing(db, p1, item_list[0].id, 1080.0, 0.49, 0.52, 0.55, 20000)
            _timing(db, p1, item_list[1].id, 720.0, 0.51, 0.50, 0.48, 15000)

        if p2:
            _snap(db, p2, "hero", hero_list[3].id, 0.532, 0.498, 15000, 0.14)
            _snap(db, p2, "hero", hero_list[4].id, 0.489, 0.524, 11000, 0.09)
            _verdict(db, p2, p2.changes[0], 0.532, 0.498, 15000, "worked",
                     "Regen nerf brought an overtuned hero down 3.4 points.", "down")
            _verdict(db, p2, p2.changes[1], 0.489, 0.524, 11000, "worked",
                     "Ultimate buff lifted a weak hero into the viable band.", "up")

        if p3:
            _snap(db, p3, "hero", hero_list[5].id, 0.505, 0.503, 18000, 0.11)
            _verdict(db, p3, p3.changes[0], 0.505, 0.503, 18000, "no_effect",
                     "Bugfix — win rate unchanged, as expected.", "none")

        db.commit()
        total_changes = sum(len(p.changes) for p in made)
        print(f"[demo] seeded {len(made)} patches, {total_changes} changes, "
              "snapshots + verdicts + timing")
    finally:
        db.close()


if __name__ == "__main__":
    main()
