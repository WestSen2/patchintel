"""M5 device-token tests: issue, bearer auth, revoke."""

from unittest import mock

from app import models
from app.personal import tokens

STEAM_ID = "76561198012345678"
CLAIMED = f"https://steamcommunity.com/openid/id/{STEAM_ID}"


def _login(client):
    params = {
        "openid.mode": "id_res",
        "openid.claimed_id": CLAIMED,
        "openid.identity": CLAIMED,
        "openid.sig": "fakesig",
    }
    with mock.patch(
        "app.api.auth.verify_openid_assertion", return_value=STEAM_ID
    ), mock.patch("app.api.auth.fetch_steam_profile", return_value={}):
        client.get("/api/auth/steam/callback", params=params, follow_redirects=False)


def test_device_token_roundtrip(client, db_session):
    _login(client)
    resp = client.post("/api/me/token")
    assert resp.status_code == 200
    token = resp.json()["token"]
    assert token.startswith("pi_")

    # plaintext is not stored
    row = db_session.query(models.DeviceToken).one()
    assert token not in row.token_hash

    # bearer auth works on /api/me (fresh client: no cookie)
    fresh = client.__class__(client.app)
    me = fresh.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["steam_id"] == STEAM_ID


def test_invalid_token_rejected(client, db_session):
    resp = client.get("/api/me", headers={"Authorization": "Bearer pi_nope"})
    assert resp.status_code == 401


def test_revoke_tokens(client, db_session):
    _login(client)
    token = client.post("/api/me/token").json()["token"]
    resp = client.delete("/api/me/token")
    assert resp.json()["revoked"] == 1
    fresh = client.__class__(client.app)
    assert fresh.get(
        "/api/me", headers={"Authorization": f"Bearer {token}"}
    ).status_code == 401


def test_token_endpoints_require_auth(client):
    assert client.post("/api/me/token").status_code == 401
    assert client.delete("/api/me/token").status_code == 401


def test_user_for_token_updates_last_used(db_session):
    user = models.User(steam_id="76561198099999999", display_name="t")
    db_session.add(user)
    db_session.commit()
    token = tokens.issue_token(db_session, user)
    found = tokens.user_for_token(db_session, token)
    assert found.id == user.id
    row = db_session.query(models.DeviceToken).one()
    assert row.last_used_at is not None
