"""Steam OpenID 2.0 login + session auth for /api/me/*.

Flow (blueprint §M3, design review §4):
1. GET /api/auth/steam/login    -> 302 to steamcommunity.com/openid/login
2. GET /api/auth/steam/callback -> verify the assertion by POSTing the params
   back with openid.mode=check_authentication, extract the SteamID64 from
   claimed_id, upsert the user, set the session cookie, redirect to UI.
3. Session lives in a signed cookie (Starlette SessionMiddleware, secret
   from APP_SECRET_KEY in .env). No JWT, no client-side token handling.

Display name/avatar come from Steam GetPlayerSummaries (uses the existing
STEAM_API_KEY); failures there never block login.
"""

from __future__ import annotations

import re
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import Settings, get_settings
from ..db import get_db

router = APIRouter(tags=["auth"])

STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"
STEAM_SUMMARIES_URL = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
_CLAIMED_ID = re.compile(r"^https://steamcommunity\.com/openid/id/(\d{17})$")


def _callback_url(settings: Settings) -> str:
    return f"{settings.app_base_url}/api/auth/steam/callback"


@router.get("/auth/steam/login")
def steam_login(settings: Settings = Depends(get_settings)):
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": _callback_url(settings),
        "openid.realm": settings.app_base_url,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return RedirectResponse(f"{STEAM_OPENID_URL}?{urlencode(params)}")


def verify_openid_assertion(params: dict[str, str]) -> str | None:
    """POST the assertion back to Steam (check_authentication).

    Returns the 17-digit SteamID64 on success, None otherwise. Split out
    for tests — this is the only network call in the callback.
    """
    payload = dict(params)
    payload["openid.mode"] = "check_authentication"
    try:
        resp = httpx.post(STEAM_OPENID_URL, data=payload, timeout=10.0)
    except httpx.HTTPError:
        return None
    if "is_valid:true" not in resp.text:
        return None
    match = _CLAIMED_ID.match(params.get("openid.claimed_id", ""))
    return match.group(1) if match else None


def fetch_steam_profile(settings: Settings, steam_id: str) -> dict[str, str]:
    """Best-effort display name + avatar; empty dict on any failure."""
    if not settings.steam_api_key:
        return {}
    try:
        resp = httpx.get(
            STEAM_SUMMARIES_URL,
            params={"key": settings.steam_api_key, "steamids": steam_id},
            timeout=10.0,
        )
        players = resp.json().get("response", {}).get("players", [])
        if players:
            return {
                "display_name": players[0].get("personaname", ""),
                "avatar_url": players[0].get("avatarfull", ""),
            }
    except Exception:
        pass
    return {}


@router.get("/auth/steam/callback")
def steam_callback(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    params = dict(request.query_params)
    steam_id = verify_openid_assertion(params)
    if steam_id is None:
        raise HTTPException(status_code=401, detail="Steam login verification failed")

    user = db.query(models.User).filter_by(steam_id=steam_id).one_or_none()
    if user is None:
        user = models.User(steam_id=steam_id)
        db.add(user)
    profile = fetch_steam_profile(settings, steam_id)
    if profile.get("display_name"):
        user.display_name = profile["display_name"]
    if profile.get("avatar_url"):
        user.avatar_url = profile["avatar_url"]
    if not user.display_name:
        user.display_name = f"Steam user {steam_id[-4:]}"
    db.commit()

    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard")


@router.post("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> models.User:
    """Dependency for /api/me/* — accepts the session cookie (website) or an
    `Authorization: Bearer` device token (M5 companion app)."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        from ..personal.tokens import user_for_token

        user = user_for_token(db, auth[7:].strip())
        if user is not None:
            return user
        raise HTTPException(status_code=401, detail="Invalid device token")

    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    user = db.get(models.User, user_id)
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Session user no longer exists")
    return user


@router.get("/me", response_model=schemas.MeOut)
def me(user: models.User = Depends(get_current_user)):
    return schemas.MeOut.model_validate(user)


@router.post("/me/token")
def create_device_token(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Issue a device token for the companion app. Shown ONCE — copy it now."""
    from ..personal.tokens import issue_token

    return {"token": issue_token(db, user)}


@router.delete("/me/token")
def revoke_device_tokens(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    from ..personal.tokens import revoke_tokens

    return {"revoked": revoke_tokens(db, user)}
