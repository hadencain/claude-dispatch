from dispatch_hub.models import Pane, Profile
from dispatch_hub.launcher import build_command, _pane_title


def _prof(layout, panes):
    return Profile.new("p", layout, panes)


def test_horizontal_two_panes_exact_command():
    prof = _prof("horizontal", [Pane("C:/a", "Backend", "go"), Pane("C:/b", "QA", "test")])
    cmd = build_command(prof, ["s0.ps1", "s1.ps1"])
    assert cmd == [
        "wt.exe",
        "new-tab", "-d", "C:/a", "--title", "Backend", "pwsh", "-NoExit", "-File", "s0.ps1",
        ";",
        "split-pane", "-V", "-d", "C:/b", "--title", "QA", "pwsh", "-NoExit", "-File", "s1.ps1",
    ]


def test_vertical_uses_horizontal_divider_flag():
    prof = _prof("vertical", [Pane("C:/a", None, ""), Pane("C:/b", None, "")])
    cmd = build_command(prof, ["s0", "s1"])
    assert "split-pane" in cmd
    # vertical layout => stacked rows => -H divider
    idx = cmd.index("split-pane")
    assert cmd[idx + 1] == "-H"


def test_title_falls_back_to_basename_when_no_role_or_title():
    assert _pane_title(Pane("C:/foo/bar", None, "")) == "bar"
    assert _pane_title(Pane("C:/foo/bar", "Frontend", "")) == "Frontend"
    assert _pane_title(Pane("C:/foo/bar", "Frontend", "", title="Custom")) == "Custom"


def test_grid_four_panes_count_and_flags():
    panes = [Pane(f"C:/p{i}", None, "") for i in range(4)]
    cmd = build_command(_prof("grid", panes), [f"s{i}" for i in range(4)])
    # four panes => one new-tab + three split-pane
    assert cmd.count("new-tab") == 1
    assert cmd.count("split-pane") == 3
    # grid emits both divider orientations, sizing, and focus moves
    assert "-V" in cmd and "-H" in cmd
    assert "--size" in cmd
    assert "move-focus" in cmd


def test_unknown_layout_raises():
    import pytest
    with pytest.raises(ValueError):
        build_command(_prof("diagonal", [Pane("C:/a", None, "")]), ["s0"])
