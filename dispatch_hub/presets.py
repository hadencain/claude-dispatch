"""Startup-prompt presets, resolved to literal strings at save time."""

PRESETS: dict[str, str | None] = {
    "continue": "Continue development on this project.",
    "workspace": "Check the workspace status for the current project.",
    "plan": "/plan",
    "custom": None,
}
