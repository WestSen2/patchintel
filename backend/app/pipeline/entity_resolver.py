"""Resolve extracted entity names -> numeric game IDs.

Names come from messy patch prose; IDs come from /v1/assets/*. Matching is
case-insensitive on normalized names. Anything unresolved keeps
entity_id=None and entity_type as extracted — never guessed (review §4).
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from .. import models

_NORMALIZE = re.compile(r"[^a-z0-9]+")


def _norm(name: str) -> str:
    return _NORMALIZE.sub("", name.lower())


class EntityResolver:
    def __init__(self, db: Session):
        self._heroes = {_norm(h.name): h.id for h in db.query(models.Hero).all()}
        self._items = {_norm(i.name): i.id for i in db.query(models.Item).all()}

    def resolve(self, entity_type: str, entity_name: str) -> int | None:
        key = _norm(entity_name)
        if not key:
            return None
        if entity_type == "hero":
            return self._heroes.get(key)
        if entity_type == "item":
            return self._items.get(key)
        # "unknown" extractions still get a chance to resolve against both
        return self._heroes.get(key) or self._items.get(key)
