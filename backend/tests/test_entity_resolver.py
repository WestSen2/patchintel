"""Entity resolver: unknown-entity rescue via source_line scanning."""

from app import models
from app.pipeline.entity_resolver import resolve_unknown_changes


def _seed(db):
    db.add(models.Hero(id=1, name="Infernus"))
    db.add(models.Item(id=10, name="Headhunter"))
    patch = models.Patch(
        steam_gid="r1", title="t", patch_date=None, source_url="u",
        raw_text="x", status="extracted",
    )
    patch.changes.append(
        models.Change(
            entity_type="unknown", entity_name="unknown", entity_id=None,
            change_type="adjustment",
            description="Infernus: Base damage reduced from 30 to 27",
            numbers=[], source_line="Infernus: Base damage reduced from 30 to 27",
        )
    )
    patch.changes.append(
        models.Change(
            entity_type="unknown", entity_name="unknown", entity_id=None,
            change_type="adjustment",
            description="Headhunter bonus reduced",
            numbers=[], source_line="Headhunter bonus reduced",
        )
    )
    patch.changes.append(
        models.Change(
            entity_type="unknown", entity_name="unknown", entity_id=None,
            change_type="adjustment",
            description="Fixed several crashes on match end",
            numbers=[], source_line="Fixed several crashes on match end",
        )
    )
    db.add(patch)
    db.commit()
    return patch


def test_resolve_unknown_changes_rescues_named_entities(db_session):
    patch = _seed(db_session)
    rescued = resolve_unknown_changes(db_session)
    assert rescued == 2

    hero_change, item_change, crash_change = patch.changes
    assert (hero_change.entity_type, hero_change.entity_id) == ("hero", 1)
    assert hero_change.entity_name == "Infernus"
    assert (item_change.entity_type, item_change.entity_id) == ("item", 10)
    # nothing found -> stays unresolved, never guessed
    assert crash_change.entity_id is None


def test_resolve_unknown_changes_is_idempotent(db_session):
    _seed(db_session)
    resolve_unknown_changes(db_session)
    assert resolve_unknown_changes(db_session) == 0
