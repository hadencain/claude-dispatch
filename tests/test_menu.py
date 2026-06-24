from dispatch_hub.menu import resolve_startup_prompt


def test_resolve_preset_returns_literal():
    assert resolve_startup_prompt("plan") == "/plan"
    assert resolve_startup_prompt("continue") == "Continue development on this project."


def test_resolve_custom_returns_user_text():
    assert resolve_startup_prompt("custom", "do the thing") == "do the thing"


from dispatch_hub.menu import proposals_to_profile
from dispatch_hub.triage import Proposal


def _prop(idx, role, directory, prompt, unresolved=False):
    return Proposal(idx, f"item{idx}", role, directory, prompt, "r", unresolved)


def test_proposals_to_profile_one_pane_each():
    props = [
        _prop(0, "QA", "C:/a", "check the pipeline"),
        _prop(1, None, "C:/b", "build the thing"),
    ]
    prof = proposals_to_profile(props)
    assert prof.layout == "grid"
    assert len(prof.panes) == 2
    assert prof.panes[0].role == "QA"
    assert prof.panes[0].directory == "C:/a"
    assert prof.panes[0].startup_prompt == "check the pipeline"
    assert prof.panes[1].role is None


from dispatch_hub.menu import App


def _app():
    # stores are unused by the guard path; None is safe because the guard
    # returns before touching them.
    return App(profiles=None, roles=None, launch_dir=None)


def test_dispatch_returns_early_without_queue_path(monkeypatch, capsys):
    app = _app()
    monkeypatch.setattr(app, "_load_settings", lambda: {})
    called = {"triage": False}
    monkeypatch.setattr("dispatch_hub.menu.classify",
                        lambda *a, **k: called.__setitem__("triage", True) or [])
    app.dispatch_from_queue()
    assert called["triage"] is False
    out = capsys.readouterr().out
    assert "work_queue_path" in out


def test_save_and_load_settings_roundtrip(tmp_path, monkeypatch):
    import dispatch_hub.menu as menu
    monkeypatch.setattr(menu, "SETTINGS_FILE", tmp_path / "settings.json")
    app = _app()
    app._save_settings({"anthropic_api_key": "sk-test", "work_queue_path": "C:/x.md"})
    loaded = app._load_settings()
    assert loaded["anthropic_api_key"] == "sk-test"
    assert loaded["work_queue_path"] == "C:/x.md"


def test_prompt_saves_entered_key_and_preserves_existing(tmp_path, monkeypatch):
    import dispatch_hub.menu as menu
    monkeypatch.setattr(menu, "SETTINGS_FILE", tmp_path / "settings.json")
    app = _app()
    settings = {"work_queue_path": "C:/x.md"}
    # asker returns a padded key; it should be stripped, saved, and returned
    result = app._prompt_and_save_api_key(settings, asker=lambda: "  sk-entered  ")
    assert result == "sk-entered"
    reloaded = app._load_settings()
    assert reloaded["anthropic_api_key"] == "sk-entered"
    assert reloaded["work_queue_path"] == "C:/x.md"  # existing setting preserved


def test_prompt_blank_key_saves_nothing(tmp_path, monkeypatch):
    import dispatch_hub.menu as menu
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(menu, "SETTINGS_FILE", settings_file)
    app = _app()
    result = app._prompt_and_save_api_key({"work_queue_path": "C:/x.md"}, asker=lambda: "")
    assert result is None
    assert not settings_file.exists()  # cancel writes nothing
