"""M3 auth tests: Steam OpenID round-trip (mocked), session, /api/me."""

from unittest import mock

from app import models

STEAM_ID = "76561198012345678"
CLAIMED = f"https://steamcommunity.com/openid/id/{STEAM_ID}"


def test_login_redirects_to_steam(client):
    resp = client.get("/api/auth/steam/login", follow_redirects=False)
    assert resp.status_code in (302, 307)
    location = resp.headers["location"]
    assert location.startswith("https://steamcommunity.com/openid/login?")
    assert "openid.mode=checkid_setup" in location


def _callback(client, **overrides):
    params = {
        "openid.mode": "id_res",
        "openid.claimed_id": CLAIMED,
        "openid.identity": CLAIMED,
        "openid.sig": "fakesig",
    }
    params.update(overrides)
    return client.get("/api/auth/steam/callback", params=params, follow_redirects=False)


def test_callback_creates_user_and_session(client, db_session):
    with mock.patch(
        "app.api.auth.verify_openid_assertion", return_value=STEAM_ID
    ), mock.patch(
        "app.api.auth.fetch_steam_profile",
        return_value={"display_name": "aiden", "avatar_url": "https://img/x.jpg"},
    ):
        resp = _callback(client)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "/dashboard"

    user = db_session.query(models.User).filter_by(steam_id=STEAM_ID).one()
    assert user.display_name == "aiden"

    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["steam_id"] == STEAM_ID


def test_callback_rejects_invalid_assertion(client, db_session):
    with mock.patch("app.api.auth.verify_openid_assertion", return_value=None):
        resp = _callback(client)
    assert resp.status_code == 401
    assert db_session.query(models.User).count() == 0


def test_callback_upserts_returning_user(client, db_session):
    with mock.patch(
        "app.api.auth.verify_openid_assertion", return_value=STEAM_ID
    ), mock.patch("app.api.auth.fetch_steam_profile", return_value={}):
        assert _callback(client).status_code in (302, 307)
        assert _callback(client).status_code in (302, 307)
    assert db_session.query(models.User).count() == 1


def test_me_requires_auth(client):
    assert client.get("/api/me").status_code == 401


def test_logout_clears_session(client, db_session):
    with mock.patch(
        "app.api.auth.verify_openid_assertion", return_value=STEAM_ID
    ), mock.patch("app.api.auth.fetch_steam_profile", return_value={}):
        _callback(client)
    assert client.get("/api/me").status_code == 200
    client.post("/api/auth/logout")
    assert client.get("/api/me").status_code == 401
