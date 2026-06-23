import pytest

from dispatch_hub.roles import RoleStore, DEFAULT_ROLES, roles_from_json
from dispatch_hub.models import Role


def test_default_roles_present():
    names = {r.name for r in DEFAULT_ROLES}
    assert names == {"Architect", "Backend", "Frontend", "QA"}
    assert all(r.builtin and r.charter for r in DEFAULT_ROLES)


def test_ensure_seeded_writes_defaults(tmp_path):
    store = RoleStore(tmp_path / "roles.json")
    store.ensure_seeded()
    assert (tmp_path / "roles.json").exists()
    assert {r.name for r in store.load()} == {"Architect", "Backend", "Frontend", "QA"}


def test_ensure_seeded_is_idempotent_and_preserves_edits(tmp_path):
    store = RoleStore(tmp_path / "roles.json")
    store.ensure_seeded()
    store.upsert(Role("Backend", "edited charter", builtin=True))
    store.ensure_seeded()  # must not overwrite
    assert store.get("Backend").charter == "edited charter"


def test_charters_returns_name_to_charter_map(tmp_path):
    store = RoleStore(tmp_path / "roles.json")
    store.ensure_seeded()
    c = store.charters()
    assert c["Architect"] == store.get("Architect").charter


def test_upsert_adds_then_delete_removes(tmp_path):
    store = RoleStore(tmp_path / "roles.json")
    store.ensure_seeded()
    store.upsert(Role("Docs", "write docs"))
    assert store.get("Docs").charter == "write docs"
    store.delete("Docs")
    assert store.get("Docs") is None


def test_roles_from_json_parses_array():
    text = '[{"name": "Security", "charter": "guard things"}, ' \
           '{"name": "Docs", "charter": "write docs", "builtin": false}]'
    roles = roles_from_json(text)
    assert [r.name for r in roles] == ["Security", "Docs"]
    assert roles[0].charter == "guard things"


def test_roles_from_json_accepts_single_object():
    roles = roles_from_json('{"name": "Security", "charter": "guard"}')
    assert len(roles) == 1 and roles[0].name == "Security"


def test_roles_from_json_forces_builtin_false():
    # imported roles are always custom, even if the JSON claims builtin
    roles = roles_from_json('[{"name": "X", "charter": "c", "builtin": true}]')
    assert roles[0].builtin is False


def test_roles_from_json_rejects_missing_fields():
    with pytest.raises(ValueError):
        roles_from_json('[{"name": "NoCharter"}]')


def test_roles_from_json_rejects_non_role_shape():
    with pytest.raises(ValueError):
        roles_from_json('"just a string"')


def test_import_roles_adds_and_updates(tmp_path):
    store = RoleStore(tmp_path / "roles.json")
    store.ensure_seeded()
    added, updated = store.import_roles([
        Role("Security", "guard"),          # new
        Role("Backend", "overridden"),      # updates a built-in
    ])
    assert (added, updated) == (1, 1)
    assert store.get("Security").charter == "guard"
    assert store.get("Backend").charter == "overridden"
