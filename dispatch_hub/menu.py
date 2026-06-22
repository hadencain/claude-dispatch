from __future__ import annotations

from pathlib import Path

import questionary
from rich.console import Console
from rich.table import Table

from .launcher import LAUNCH_DIR_NAME, launch
from .models import Pane, Profile, Role
from .presets import PRESETS
from .roles import RoleStore
from .store import ProfileStore
from .validation import check_tooling, validate_directories, validate_profile_name

CONFIG_DIR = Path("config")
PROFILES_DIR = CONFIG_DIR / "profiles"
ROLES_FILE = CONFIG_DIR / "roles.json"
LAUNCH_DIR = CONFIG_DIR / LAUNCH_DIR_NAME

console = Console()


def resolve_startup_prompt(choice: str, custom_text: str = "") -> str:
    if choice == "custom":
        return custom_text
    value = PRESETS.get(choice)
    return value if value is not None else ""


class App:
    def __init__(self, profiles: ProfileStore, roles: RoleStore, launch_dir: Path):
        self.profiles = profiles
        self.roles = roles
        self.launch_dir = launch_dir

    # ---- review rendering ----
    def _review_table(self, profile: Profile) -> Table:
        table = Table(title=f"{profile.name}  [{profile.layout}]")
        table.add_column("#"); table.add_column("Directory")
        table.add_column("Role"); table.add_column("Startup prompt")
        for i, p in enumerate(profile.panes):
            table.add_row(str(i), p.directory, p.role or "-", p.startup_prompt or "-")
        return table

    # ---- flows ----
    def launch_session(self) -> None:
        name = self._pick_profile("Launch which profile?")
        if not name:
            return
        profile = self.profiles.load(name)
        if not profile.panes:
            console.print(f"[red]Profile '{name}' has no panes; nothing to launch.[/red]")
            return
        missing_tools = check_tooling()
        if missing_tools:
            console.print(f"[red]Missing tools on PATH: {', '.join(missing_tools)}.[/red]")
            console.print("Install/expose them and try again.")
            return
        missing_dirs = validate_directories(profile)
        if missing_dirs:
            console.print("[red]These directories do not exist:[/red]")
            for d in missing_dirs:
                console.print(f"  - {d}")
            return
        console.print(self._review_table(profile))
        if questionary.confirm("Launch this session?").ask():
            launch(profile, self.roles.charters(), self.launch_dir)
            console.print("[green]Launched.[/green]")

    def create_session(self) -> None:
        existing = self.profiles.list()
        name = questionary.text("Profile name:").ask()
        err = validate_profile_name(name or "", existing)
        if err:
            console.print(f"[red]{err}[/red]")
            return
        layout = questionary.select(
            "Layout:", choices=["vertical", "horizontal", "grid"]
        ).ask()
        if layout is None:
            return
        panes: list[Pane] = []
        role_names = [r.name for r in self.roles.load()]
        while True:
            directory = questionary.text("Project directory:").ask()
            if directory is None:
                return
            role = questionary.select(
                "Role:", choices=["(none)"] + role_names
            ).ask()
            if role is None:
                return
            role = None if role == "(none)" else role
            choice = questionary.select(
                "Startup prompt:",
                choices=["continue", "workspace", "plan", "custom"],
            ).ask()
            if choice is None:
                return
            custom = ""
            if choice == "custom":
                custom = questionary.text("Custom prompt:").ask() or ""
            panes.append(Pane(directory, role, resolve_startup_prompt(choice, custom)))
            if not questionary.confirm("Add another pane?").ask():
                break
        profile = Profile.new(name, layout, panes)
        console.print(self._review_table(profile))
        if questionary.confirm("Save this profile?").ask():
            self.profiles.save(profile)
            console.print(f"[green]Saved '{name}'.[/green]")

    def delete_session(self) -> None:
        name = self._pick_profile("Delete which profile?")
        if not name:
            return
        if questionary.confirm(f"Delete '{name}'?").ask():
            self.profiles.delete(name)
            console.print(f"[green]Deleted '{name}'.[/green]")

    def _roles_table(self, roles: list[Role]) -> Table:
        table = Table(title="Roles")
        table.add_column("Name"); table.add_column("Built-in"); table.add_column("Charter")
        for r in roles:
            charter = r.charter if len(r.charter) <= 60 else r.charter[:59] + "…"
            table.add_row(r.name, "yes" if r.builtin else "no", charter)
        return table

    def manage_roles(self) -> None:
        while True:
            roles = self.roles.load()
            console.print(self._roles_table(roles))
            action = questionary.select(
                "Manage roles:",
                choices=["Edit a charter", "Add a role", "Delete a custom role", "Back"],
            ).ask()
            if action in (None, "Back"):
                return
            if action == "Edit a charter":
                name = questionary.select(
                    "Edit which role?", choices=[r.name for r in roles]
                ).ask()
                if name is None:
                    continue
                current = self.roles.get(name)
                new_charter = questionary.text(
                    "Charter:", default=current.charter, multiline=True
                ).ask()
                if new_charter is None or not new_charter.strip():
                    console.print("[yellow]No change.[/yellow]")
                    continue
                self.roles.upsert(Role(name, new_charter, builtin=current.builtin))
                console.print(f"[green]Updated '{name}'.[/green]")
            elif action == "Add a role":
                name = questionary.text("New role name:").ask()
                if not name or not name.strip():
                    continue
                name = name.strip()
                if self.roles.get(name):
                    console.print(f"[red]A role named '{name}' already exists.[/red]")
                    continue
                charter = questionary.text("Charter:", multiline=True).ask()
                if charter is None or not charter.strip():
                    console.print("[yellow]Cancelled; role not added.[/yellow]")
                    continue
                self.roles.upsert(Role(name, charter, builtin=False))
                console.print(f"[green]Added '{name}'.[/green]")
            elif action == "Delete a custom role":
                customs = [r.name for r in roles if not r.builtin]
                if not customs:
                    console.print("[yellow]No custom roles to delete (built-ins are protected).[/yellow]")
                    continue
                name = questionary.select(
                    "Delete which custom role?", choices=customs
                ).ask()
                if name is None:
                    continue
                if questionary.confirm(f"Delete '{name}'?").ask():
                    self.roles.delete(name)
                    console.print(f"[green]Deleted '{name}'.[/green]")

    def _pick_profile(self, prompt: str) -> str | None:
        names = self.profiles.list()
        if not names:
            console.print("[yellow]No saved profiles yet.[/yellow]")
            return None
        return questionary.select(prompt, choices=names).ask()

    def run(self) -> None:
        actions = {
            "Launch session": self.launch_session,
            "Create session": self.create_session,
            "Delete session": self.delete_session,
            "Manage roles": self.manage_roles,
        }
        while True:
            choice = questionary.select(
                "Claude Dispatch Hub", choices=list(actions) + ["Quit"]
            ).ask()
            if choice in (None, "Quit"):
                break
            actions[choice]()
