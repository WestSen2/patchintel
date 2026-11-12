"""API + server-rendered UI smoke tests over seeded data."""

from datetime import datetime

from app import models


def _seed(db):
    patch = models.Patch(
        steam_gid="g1",
        title="Deadlock - Gameplay Update - 01-01-2026",
        patch_date=datetime(2026, 1, 1),
        source_url="https://forums.playdeadlock.com/threads/g1",
        raw_text="Warden: Base movement speed reduced from 6.5 to 6",
        status="extracted",
        summary="Warden got slowed down.",
        llm_generated=True,
    )
    patch.changes.append(
        models.Change(
            entity_type="hero",
            entity_name="Warden",
            entity_id=None,
            change_type="nerf",
            description="Base movement speed reduced.",
            numbers=[{"stat": "Base movement speed", "old": "6.5", "new": "6", "unit": ""}],
            source_line="Warden: Base movement speed reduced from 6.5 to 6",
        )
    )
    db.add(patch)
    db.commit()
    return patch


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_patches(client, db_session):
    _seed(db_session)
    resp = client.get("/api/patches")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["change_count"] == 1
    assert data[0]["status"] == "extracted"


def test_patch_detail(client, db_session):
    patch = _seed(db_session)
    resp = client.get(f"/api/patches/{patch.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["changes"][0]["entity_name"] == "Warden"
    assert data["changes"][0]["numbers"][0]["new"] == "6"


def test_patch_detail_404(client):
    assert client.get("/api/patches/999").status_code == 404


def test_ui_pages_render(client, db_session):
    patch = _seed(db_session)
    assert client.get("/").status_code == 200
    resp = client.get(f"/patches/{patch.id}")
    assert resp.status_code == 200
    assert "Warden" in resp.text


def _seed_impact(db):
    patch = _seed(db)
    change = patch.changes[0]
    db.add(
        models.Verdict(
            patch_id=patch.id,
            change_id=change.id,
            entity_type="hero",
            entity_id=7,
            expected_direction="down",
            pre_win_rate=0.52,
            post_win_rate=0.48,
            delta_win_rate=-0.04,
            pre_pick_rate=0.10,
            post_pick_rate=0.11,
            pre_matches=1200,
            post_matches=1400,
            ci_half_width=0.015,
            verdict="worked",
            reason="Win rate moved in the expected direction beyond the 95% CI.",
        )
    )
    db.commit()
    return patch


def test_patch_impact(client, db_session):
    patch = _seed_impact(db_session)
    resp = client.get(f"/api/patches/{patch.id}/impact")
    assert resp.status_code == 200
    data = resp.json()
    assert data["patch_id"] == patch.id
    assert len(data["verdicts"]) == 1
    v = data["verdicts"][0]
    assert v["verdict"] == "worked"
    assert v["delta_win_rate"] == -0.04
    assert v["expected_direction"] == "down"


def test_patch_impact_empty(client, db_session):
    patch = _seed(db_session)
    resp = client.get(f"/api/patches/{patch.id}/impact")
    assert resp.status_code == 200
    assert resp.json()["verdicts"] == []


def test_patch_impact_404(client):
    assert client.get("/api/patches/999/impact").status_code == 404


def test_item_purchase_curve_cached(client, db_session, monkeypatch):
    db_session.add(models.Item(id=42, name="Headhunter", tier=3, cost=3500))
    db_session.commit()

    calls = []

    def fake_item_stats(settings, start=None, end=None, **kwargs):
        calls.append(kwargs)
        return [{"item_id": 42, "wins": 60, "losses": 40, "matches": 100}]

    monkeypatch.setattr(
        "app.upstream.deadlock_analytics.item_stats", fake_item_stats
    )
    monkeypatch.setattr(
        "app.api.stats.deadlock_analytics.item_stats", fake_item_stats
    )

    resp = client.get("/api/items/42/purchase-curve")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 25  # 3000s / 120s slices
    assert data[0]["bucket_start_s"] == 0
    assert data[0]["win_rate"] == 0.6
    first_call_count = len(calls)
    assert first_call_count == 25

    # second request served from cache — no new upstream calls
    resp2 = client.get("/api/items/42/purchase-curve")
    assert resp2.status_code == 200
    assert len(calls) == first_call_count


def test_item_purchase_curve_404(client):
    assert client.get("/api/items/999/purchase-curve").status_code == 404
