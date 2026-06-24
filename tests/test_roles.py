from dispatch_hub.roles import RoleStore, DEFAULT_ROLES
from dispatch_hub.models import Role


DEFAULT_NAMES = {
    "Architect", "Backend", "Frontend", "QA",
    "Security", "Performance", "Data", "DevOps", "Docs", "Research",
}


def test_default_roles_present():
    names = {r.name for r in DEFAULT_ROLES}
    assert names == DEFAULT_NAMES
    assert all(r.charter for r in DEFAULT_ROLES)


def test_ensure_seeded_writes_defaults(tmp_path):
    store = RoleStore(tmp_path / "roles.json")
    store.ensure_seeded()
    assert (tmp_path / "roles.json").exists()
    assert {r.name for r in store.load()} == DEFAULT_NAMES


def test_ensure_seeded_is_idempotent_and_preserves_edits(tmp_path):
    store = RoleStore(tmp_path / "roles.json")
    store.ensure_seeded()
    store.upsert(Role("Backend", "edited charter"))
    store.ensure_seeded()  # must not overwrite
    assert store.get("Backend").charter == "edited charter"


def test_charters_returns_name_to_charter_map(tmp_path):
    store = RoleStore(tmp_path / "roles.json")
    store.ensure_seeded()
    c = store.charters()
    assert c["Architect"] == store.get("Architect").charter


def test_upsert_updates_existing_charter(tmp_path):
    store = RoleStore(tmp_path / "roles.json")
    store.ensure_seeded()
    store.upsert(Role("Docs", "rewritten charter"))
    assert store.get("Docs").charter == "rewritten charter"
    # name set is unchanged — upsert replaces in place, never grows the defaults
    assert {r.name for r in store.load()} == DEFAULT_NAMES
