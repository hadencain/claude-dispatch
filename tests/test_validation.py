from dispatch_hub.validation import (
    validate_directories, check_tooling, validate_profile_name,
)
from dispatch_hub.models import Profile, Pane


def test_validate_directories_flags_missing(tmp_path):
    good = str(tmp_path)
    prof = Profile.new("p", "grid", [Pane(good, None, ""), Pane("C:/nope_xyz", None, "")])
    missing = validate_directories(prof)
    assert missing == ["C:/nope_xyz"]


def test_validate_directories_all_present(tmp_path):
    prof = Profile.new("p", "grid", [Pane(str(tmp_path), None, "")])
    assert validate_directories(prof) == []


def test_check_tooling_reports_missing_claude():
    def fake_which(name):
        return "C:/wt.exe" if name == "wt.exe" else None
    assert check_tooling(which=fake_which) == ["claude"]


def test_check_tooling_all_present():
    assert check_tooling(which=lambda n: "found") == []


def test_validate_profile_name_rules():
    assert validate_profile_name("", []) is not None          # empty
    assert validate_profile_name("a/b", []) is not None       # unsafe char
    assert validate_profile_name("dup", ["dup"]) is not None  # collision
    assert validate_profile_name("ok-name_1", ["other"]) is None
