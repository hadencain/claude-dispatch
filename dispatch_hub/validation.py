from __future__ import annotations

import os
import re
import shutil

from .models import Profile

REQUIRED_TOOLS = ["wt.exe", "claude"]
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def validate_directories(profile: Profile) -> list[str]:
    missing: list[str] = []
    for pane in profile.panes:
        if not os.path.isdir(pane.directory):
            missing.append(pane.directory)
    return missing


def check_tooling(which=shutil.which) -> list[str]:
    missing = [tool for tool in REQUIRED_TOOLS if which(tool) is None]
    # Panes are spawned via PowerShell; pwsh (PS7) is preferred but not on
    # stock Windows, so powershell.exe (PS5.1) is an acceptable fallback.
    # Only a problem if neither exists.
    if which("pwsh") is None and which("powershell") is None:
        missing.append("powershell")
    return missing


def validate_profile_name(name: str, existing: list[str]) -> str | None:
    if not name or not name.strip():
        return "Profile name cannot be empty."
    if not _SAFE_NAME.match(name):
        return "Use only letters, digits, dot, dash, underscore (no spaces or slashes)."
    if name in existing:
        return f"A profile named '{name}' already exists."
    return None
