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
        heroes = db.query(models.Hero).all()
        items = db.query(models.Item).all()
        self._heroes = {_norm(h.name): h.id for h in heroes}
        self._items = {_norm(i.name): i.id for i in items}
        self._hero_names = [(h.name, h.id) for h in heroes]
        self._item_names = [(i.name, i.id) for i in items]

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

    def find_in_text(self, text: str) -> tuple[str, str, int] | None:
        """Find a known hero/item name appearing verbatim in free text.

        Used to rescue NullSummarizer changes whose entity_name is "unknown":
        the source_line (e.g. "Infernus: Base damage reduced from 30 to 27")
        usually names the entity directly. Longest name first so multi-word
        names win over coincidental substrings.
        """
        lowered = text.lower()
        names = (
            [(n, "hero", i) for n, i in self._hero_names]
            + [(n, "item", i) for n, i in self._item_names]
        )
        for name, entity_type, entity_id in sorted(names, key=lambda t: -len(t[0])):
            if name.lower() in lowered:
                return entity_type, name, entity_id
        return None


def resolve_unknown_changes(db: Session) -> int:
    """Backfill entity fields on changes stored with entity_name 'unknown'
    (or a NULL entity_id) by scanning their source_line for known names.

    Returns how many changes were rescued. Idempotent.
    """
    resolver = EntityResolver(db)
    pending = (
        db.query(models.Change)
        .filter(
            (models.Change.entity_id.is_(None))
            | (models.Change.entity_name == "unknown")
        )
        .all()
    )
    rescued = 0
    for change in pending:
        found = resolver.find_in_text(change.source_line or change.description)
        if found is None:
            continue
        change.entity_type, change.entity_name, change.entity_id = found
        rescued += 1
    db.commit()
    return rescued
