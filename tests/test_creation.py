from pathlib import Path
import pytest
from dispatch_hub.creation import (
    sanitize_dirname, candidate_parents, target_path,
    validate_new_dir, create_directory,
)


def test_sanitize_collapses_spaces_and_keeps_case():
    assert sanitize_dirname("Distortion plugins") == "Distortion-plugins"


def test_sanitize_strips_illegal_chars():
    assert sanitize_dirname('a/b:c?') == "a-b-c"


def test_sanitize_empty_when_nothing_usable():
    assert sanitize_dirname("   ") == ""
    assert sanitize_dirname("...") == ""


def test_candidate_parents_includes_root_and_bucket(tmp_path):
    proj = tmp_path / "src" / "pyfiles" / "thing"
    parents = candidate_parents(tmp_path, [proj])
    assert tmp_path in parents
    assert tmp_path / "src" / "pyfiles" in parents


def test_candidate_parents_excludes_outside_root(tmp_path):
    outside = tmp_path.parent / "elsewhere" / "proj"
    assert candidate_parents(tmp_path, [outside]) == [tmp_path]


def test_target_path_joins_sanitized_name(tmp_path):
    assert target_path(tmp_path, "New Thing") == tmp_path / "New-Thing"


def test_validate_rejects_empty_name(tmp_path):
    assert validate_new_dir(tmp_path, "   ", tmp_path) is not None


def test_validate_rejects_existing(tmp_path):
    (tmp_path / "dup").mkdir()
    assert validate_new_dir(tmp_path, "dup", tmp_path) is not None


def test_validate_rejects_parent_outside_root(tmp_path):
    assert validate_new_dir(tmp_path.parent, "x", tmp_path) is not None


def test_validate_ok_returns_none(tmp_path):
    assert validate_new_dir(tmp_path, "fresh", tmp_path) is None


def test_create_directory_makes_nested_dir(tmp_path):
    t = tmp_path / "a" / "b"
    create_directory(t)
    assert t.is_dir()


def test_create_directory_raises_on_existing(tmp_path):
    (tmp_path / "x").mkdir()
    with pytest.raises(FileExistsError):
        create_directory(tmp_path / "x")
