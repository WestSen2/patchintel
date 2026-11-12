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
