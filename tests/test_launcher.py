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


from pathlib import Path
from dispatch_hub.launcher import (
    render_pane_script, write_pane_scripts, sweep_stale_scripts, launch,
)


def test_render_script_with_role_embeds_charter_verbatim():
    pane = Pane("C:/a", "Backend", "go")
    charter = 'Use "quotes" and /slashes/ freely.'
    script = render_pane_script(pane, charter)
    assert charter in script                      # verbatim, no escaping mangling
    assert "--append-system-prompt $charter" in script
    assert "Set-Location -LiteralPath 'C:/a'" in script
    assert "$PSCommandPath" in script             # self-delete present


def test_render_script_no_role_omits_charter():
    script = render_pane_script(Pane("C:/a", None, "hello"), None)
    assert "--append-system-prompt" not in script
    assert "$charter" not in script
    assert "claude $prompt" in script


def test_render_script_no_prompt_omits_prompt_arg():
    script = render_pane_script(Pane("C:/a", None, ""), None)
    assert script.rstrip().endswith("claude")


def test_write_pane_scripts_creates_one_file_per_pane(tmp_path):
    prof = Profile.new("sprint", "horizontal",
                       [Pane("C:/a", "Backend", "go"), Pane("C:/b", None, "")])
    paths = write_pane_scripts(prof, {"Backend": "be backend"}, tmp_path)
    assert len(paths) == 2
    assert all(p.exists() and p.suffix == ".ps1" for p in paths)


def test_sweep_removes_stale_scripts(tmp_path):
    (tmp_path / "old.ps1").write_text("x")
    sweep_stale_scripts(tmp_path)
    assert list(tmp_path.glob("*.ps1")) == []


def test_launch_invokes_runner_with_wt_command(tmp_path):
    prof = Profile.new("p", "horizontal", [Pane("C:/a", None, "go")])
    captured = {}

    def fake_runner(cmd, **kwargs):
        captured["cmd"] = cmd
        return "ran"

    result = launch(prof, {}, tmp_path, runner=fake_runner)
    assert result == "ran"
    assert captured["cmd"][0] == "wt.exe"
    assert "new-tab" in captured["cmd"]
