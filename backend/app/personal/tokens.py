"""Device tokens for the M5 companion app.

The desktop app can't easily carry the session cookie through Steam's OpenID
redirect dance, so: the user logs into the website normally, then requests a
device token (from a settings page or the app's "pair this device" flow) and
pastes it into the app. The app sends it as `Authorization: Bearer <token>`.

Tokens are random 256-bit strings, stored SHA-256-hashed — a DB leak does not
leak usable tokens. `get_current_user` accepts either the session cookie or a
bearer token.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(db: Session, user: models.User) -> str:
    """Create a new device token; returns the PLAINTEXT token exactly once."""
    token = f"pi_{secrets.token_urlsafe(32)}"
    db.add(
        models.DeviceToken(
            user_id=user.id,
            token_hash=_hash(token),
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    db.commit()
    return token


def user_for_token(db: Session, token: str) -> models.User | None:
    row = (
        db.query(models.DeviceToken)
        .filter_by(token_hash=_hash(token))
        .one_or_none()
    )
    if row is None:
        return None
    row.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return db.get(models.User, row.user_id)


def revoke_tokens(db: Session, user: models.User) -> int:
    n = db.query(models.DeviceToken).filter_by(user_id=user.id).delete()
    db.commit()
    return n
