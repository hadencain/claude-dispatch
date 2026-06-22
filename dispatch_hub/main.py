from __future__ import annotations

from .menu import App, CONFIG_DIR, LAUNCH_DIR, PROFILES_DIR, ROLES_FILE
from .roles import RoleStore
from .store import ProfileStore


def main() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    roles = RoleStore(ROLES_FILE)
    roles.ensure_seeded()
    app = App(ProfileStore(PROFILES_DIR), roles, LAUNCH_DIR)
    app.run()


if __name__ == "__main__":
    main()
