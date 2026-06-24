from __future__ import annotations

import sys

from .menu import App, CONFIG_DIR, LAUNCH_DIR, PROFILES_DIR, ROLES_FILE
from .roles import RoleStore
from .store import ProfileStore


def _force_utf8() -> None:
    """The splash uses Unicode block glyphs; make sure the console can encode
    them even on a legacy code page (e.g. stock powershell.exe at cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass


def main() -> None:
    _force_utf8()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    roles = RoleStore(ROLES_FILE)
    roles.ensure_seeded()
    app = App(ProfileStore(PROFILES_DIR), roles, LAUNCH_DIR)
    app.run()


if __name__ == "__main__":
    main()
