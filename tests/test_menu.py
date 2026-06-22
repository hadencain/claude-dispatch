from dispatch_hub.menu import resolve_startup_prompt


def test_resolve_preset_returns_literal():
    assert resolve_startup_prompt("plan") == "/plan"
    assert resolve_startup_prompt("continue") == "Continue development on this project."


def test_resolve_custom_returns_user_text():
    assert resolve_startup_prompt("custom", "do the thing") == "do the thing"
