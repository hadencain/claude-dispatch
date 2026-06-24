from dispatch_hub.models import Role, Pane, Profile
from dispatch_hub.presets import PRESETS


def test_role_roundtrip():
    r = Role(name="Backend", charter="Be backend.")
    assert Role.from_dict(r.to_dict()) == r


def test_pane_roundtrip_with_none_role():
    p = Pane(directory="C:/proj", role=None, startup_prompt="/plan")
    d = p.to_dict()
    assert d["role"] is None
    assert Pane.from_dict(d) == p


def test_profile_roundtrip_nested_panes():
    prof = Profile.new(
        "sprint", "horizontal",
        [Pane("C:/a", "Backend", "go"), Pane("C:/b", None, "/plan")],
    )
    back = Profile.from_dict(prof.to_dict())
    assert back == prof
    assert back.created and back.modified


def test_profile_new_stamps_timestamps():
    prof = Profile.new("x", "grid", [])
    assert prof.created == prof.modified


def test_presets_resolve_to_strings():
    assert PRESETS["plan"] == "/plan"
    assert PRESETS["custom"] is None
