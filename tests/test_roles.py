from dispatch_hub.roles import RoleStore, DEFAULT_ROLES
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
