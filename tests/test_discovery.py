from dispatch_hub.discovery import discover_projects


def _mk(path, marker="requirements.txt"):
    path.mkdir(parents=True, exist_ok=True)
    (path / marker).write_text("", encoding="utf-8")


def test_finds_marked_dirs(tmp_path):
    _mk(tmp_path / "api", "package.json")
    _mk(tmp_path / "nested" / "ui", "CLAUDE.md")
    (tmp_path / "empty").mkdir()
    found = {p.relative_to(tmp_path).as_posix() for p in discover_projects(tmp_path)}
    assert found == {"api", "nested/ui"}


def test_prunes_excluded_dirs(tmp_path):
    _mk(tmp_path / "proj")
    # markers inside an excluded dir must not surface
    _mk(tmp_path / "proj" / "node_modules" / "dep", "package.json")
    _mk(tmp_path / "proj" / "venv" / "lib", "pyproject.toml")
    found = {p.relative_to(tmp_path).as_posix() for p in discover_projects(tmp_path)}
    assert found == {"proj"}


def test_respects_max_depth(tmp_path):
    _mk(tmp_path / "a" / "b" / "c" / "deep")
    assert discover_projects(tmp_path, max_depth=2) == []
    assert tmp_path / "a" / "b" / "c" / "deep" in discover_projects(tmp_path, max_depth=4)


def test_missing_root_returns_empty(tmp_path):
    assert discover_projects(tmp_path / "nope") == []
