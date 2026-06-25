from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import questionary
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import queue as workqueue
from .anthropic_client import NoApiKey, TriageClient, resolve_api_key
from .discovery import default_workspace_root, discover_projects
from .launcher import LAUNCH_DIR_NAME, launch
from .models import Pane, Profile, Role
from .presets import PRESETS
from .roles import RoleStore
from .store import ProfileStore
from .theme import MARK, STYLE, print_splash
from .triage import DEFAULT_MODEL, Proposal, classify
from .validation import check_tooling, validate_directories, validate_profile_name

CONFIG_DIR = Path("config")
PROFILES_DIR = CONFIG_DIR / "profiles"
ROLES_FILE = CONFIG_DIR / "roles.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
LAUNCH_DIR = CONFIG_DIR / LAUNCH_DIR_NAME

# Sentinel: a picker step the user backed out of rather than answered.
BACK = object()
_MANUAL_DIR = "\x00manual"
_BACK_CHOICE = "\x00back"

console = Console()


def _escape_bindings() -> KeyBindings:
    """A binding set where Esc cancels the prompt (exits with None)."""
    kb = KeyBindings()

    @kb.add(Keys.Escape)
    def _(event):
        event.app.exit(result=None)

    return kb


def ask_select(*args, **kwargs):
    """questionary.select, but Esc cancels it (returns None) like Ctrl-C.

    select() builds its own mutable KeyBindings and exposes it on the
    application, so we add an Escape binding to it before running.
    """
    kwargs.setdefault("style", STYLE)
    kwargs.setdefault("qmark", MARK)
    q = questionary.select(*args, **kwargs)

    @q.application.key_bindings.add(Keys.Escape)
    def _(event):
        event.app.exit(result=None)

    return q.ask()


def ask_text(message: str, default: str = "") -> str | None:
    """questionary.text, but Esc cancels it (returns None) like Ctrl-C.

    text() forwards kwargs to prompt_toolkit's PromptSession, so the Escape
    binding is injected via key_bindings (its app binding set is merged and
    not directly mutable).
    """
    return questionary.text(
        message, default=default, key_bindings=_escape_bindings(),
        style=STYLE, qmark=MARK,
    ).ask()


def ask_confirm(message: str) -> bool | None:
    """questionary.confirm with the shared accent style."""
    return questionary.confirm(message, style=STYLE, qmark=MARK).ask()


def ask_select_back(message: str, choices: list, **kwargs):
    """A select that always offers an explicit '← Back' choice.

    Returns BACK if the user picks Back (or escapes), else the chosen value.
    This is the reliable back path; Esc support is best-effort on top.
    """
    opts = list(choices) + [questionary.Choice("← Back", _BACK_CHOICE)]
    ans = ask_select(message, choices=opts, **kwargs)
    return BACK if ans in (None, _BACK_CHOICE) else ans


def resolve_startup_prompt(choice: str, custom_text: str = "") -> str:
    if choice == "custom":
        return custom_text
    value = PRESETS.get(choice)
    return value if value is not None else ""


def proposals_to_profile(proposals: list[Proposal], name: str = "queue-dispatch",
                         layout: str = "grid") -> Profile:
    panes = [Pane(p.directory, p.role, p.startup_prompt) for p in proposals]
    return Profile.new(name, layout, panes)


class App:
    def __init__(self, profiles: ProfileStore, roles: RoleStore, launch_dir: Path):
        self.profiles = profiles
        self.roles = roles
        self.launch_dir = launch_dir
        self._projects: list | None = None  # cached project scan (one per session)

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
        if ask_confirm("Launch this session?"):
            launch(profile, self.roles.charters(), self.launch_dir)
            console.print("[green]Launched.[/green]")

    def _load_settings(self) -> dict:
        if SETTINGS_FILE.exists():
            try:
                return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_settings(self, settings: dict) -> None:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")

    def _prompt_and_save_api_key(self, settings: dict, asker=None) -> str | None:
        """Prompt once for an Anthropic key and persist it to settings.json.

        Called only when no key resolves from env or settings. The key is
        stored in config/settings.json (gitignored) so it is entered once and
        reused on every later run. ``asker`` is injectable for testing;
        by default it reads a masked line from the terminal.
        """
        if asker is None:
            asker = lambda: questionary.password(
                "Paste your Anthropic API key (blank to cancel):",
                style=STYLE, qmark=MARK,
            ).ask()
        console.print("[yellow]No Anthropic API key found.[/yellow]")
        key = asker()
        if not key or not key.strip():
            console.print(
                "[yellow]No key entered; cannot dispatch. Rerun to enter it, "
                "or set the ANTHROPIC_API_KEY environment variable.[/yellow]"
            )
            return None
        key = key.strip()
        settings["anthropic_api_key"] = key
        self._save_settings(settings)
        console.print(
            "[green]Saved key to config/settings.json (gitignored). "
            "You won't be asked again.[/green]"
        )
        return key

    def dispatch_from_queue(self) -> None:
        settings = self._load_settings()
        queue_path = (settings.get("work_queue_path") or "").strip()
        if not queue_path:
            console.print(
                "[yellow]Set 'work_queue_path' in config/settings.json to use "
                "Dispatch from queue.[/yellow]"
            )
            return
        try:
            text = Path(queue_path).read_text(encoding="utf-8")
        except OSError as exc:
            console.print(f"[red]Could not read work queue at {queue_path}: {exc}[/red]")
            return

        items = workqueue.read_queued(text)
        if not items:
            console.print("[yellow]Queue has no items to dispatch.[/yellow]")
            return

        chosen = questionary.checkbox(
            "Select items to dispatch:",
            choices=[questionary.Choice(it.text, value=it) for it in items],
            instruction="(↑/↓ move · Space to select · Enter to confirm)",
            style=STYLE, qmark=MARK,
        ).ask()
        if chosen is None:
            return  # Esc / Ctrl-C — cancelled, no message
        if not chosen:
            # Enter pressed with nothing toggled. A checkbox does not select the
            # highlighted row on Enter, so this is the easy mistake to make.
            console.print(
                "[yellow]No items selected. Highlight an item and press [bold]Space[/bold] "
                "to select it, then [bold]Enter[/bold] to dispatch.[/yellow]"
            )
            return

        try:
            api_key = resolve_api_key(settings)
        except NoApiKey:
            api_key = self._prompt_and_save_api_key(settings)
            if not api_key:
                return

        client = TriageClient(api_key, settings.get("triage_model") or DEFAULT_MODEL)
        role_names = [r.name for r in self.roles.load()]
        root = self._workspace_root()
        if self._projects is None:
            self._projects = discover_projects(root)
        directories = [p.as_posix() for p in self._projects]

        try:
            proposals = classify([it.text for it in chosen], role_names, directories, client)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            return

        profile = proposals_to_profile(proposals)
        console.print(self._review_table(profile))
        if any(p.unresolved for p in proposals):
            console.print(
                "[red]Some items have an unresolved directory (not in the project "
                "list). Edit settings/roles or rerun; launch is blocked.[/red]"
            )
            return
        if not ask_confirm("Launch this dispatch?"):
            return

        missing_dirs = validate_directories(profile)
        if missing_dirs:
            console.print("[red]These directories do not exist:[/red]")
            for d in missing_dirs:
                console.print(f"  - {d}")
            return

        launch(profile, self.roles.charters(), self.launch_dir)
        console.print("[green]Launched.[/green]")

        dispatched_raw = [it.raw for it in chosen]
        new_text = workqueue.move_to_in_progress(text, dispatched_raw, date.today().isoformat())
        try:
            Path(queue_path).write_text(new_text, encoding="utf-8")
            console.print("[green]Moved dispatched items to In Progress.[/green]")
        except OSError as exc:
            console.print(f"[yellow]Launched, but could not update the queue file: {exc}[/yellow]")

    # ---- directory / prompt pickers ----
    def _workspace_root(self) -> Path:
        wr = self._load_settings().get("workspace_root")
        return Path(wr) if wr else default_workspace_root()

    def _pick_directory(self, default: str | None):
        """Flat searchable list of discovered projects, plus manual entry.

        Returns a path string, or BACK if the user escaped out.
        """
        root = self._workspace_root()
        if self._projects is None:
            self._projects = discover_projects(root)
        choices = []
        for p in self._projects:
            try:
                rel = root.name if p == root else p.relative_to(root).as_posix()
            except ValueError:
                rel = p.as_posix()
            choices.append(questionary.Choice(title=rel, value=p.as_posix()))
        choices.append(questionary.Choice(title="✎ Type a path manually", value=_MANUAL_DIR))
        ans = ask_select_back(
            "Project directory (type to filter):",
            choices=choices,
            use_search_filter=True,
            use_jk_keys=False,
        )
        if ans is BACK:
            return BACK
        if ans == _MANUAL_DIR:
            typed = ask_text("Project directory (blank to go back):", default=default or "")
            if typed is None or not typed.strip():
                return BACK
            return typed.strip().replace("\\", "/")
        return ans

    def _pick_startup_prompt(self, default: str | None):
        """Startup-prompt picker with the resolved text shown inline.

        Returns a preset key, or BACK if the user escaped out.
        """
        order = ["continue", "workspace", "plan", "custom"]
        choices = []
        for k in order:
            v = PRESETS.get(k)
            preview = v if v is not None else "(type your own)"
            choices.append(questionary.Choice(title=f"{k:<9} → {preview}", value=k))
        return ask_select_back(
            "Startup prompt:",
            choices=choices,
            default=default if default in order else "continue",
        )

    @staticmethod
    def _build_pane(cur: dict) -> Pane:
        role = None if cur["role"] == "(none)" else cur["role"]
        prompt = resolve_startup_prompt(cur["pkey"], cur.get("pcustom", ""))
        return Pane(cur["dir"], role, prompt)

    def create_session(self) -> None:
        existing = self.profiles.list()
        name: str | None = None
        layout: str | None = None
        panes: list[Pane] = []
        cur: dict = {}
        state = "name"

        while True:
            if state == "name":
                ans = ask_text("Profile name (blank to cancel):", default=name or "")
                if ans is None or not ans.strip():
                    return  # blank / Esc at the first field exits to the main menu
                ans = ans.strip()
                err = validate_profile_name(ans, existing)
                if err:
                    console.print(f"[red]{err}[/red]")
                    name = ans
                    continue
                name, state = ans, "layout"

            elif state == "layout":
                ans = ask_select_back(
                    "Layout:", ["vertical", "horizontal", "grid"],
                    default=layout or "vertical",
                )
                if ans is BACK:
                    state = "name"; continue
                layout, state = ans, "pane_dir"

            elif state == "pane_dir":
                d = self._pick_directory(cur.get("dir"))
                if d is BACK:
                    # First field of a pane: backing out ends pane-building.
                    cur = {}
                    state = "review" if panes else "layout"
                    continue
                cur["dir"], state = d, "pane_role"

            elif state == "pane_role":
                role_names = [r.name for r in self.roles.load()]
                ans = ask_select_back(
                    "Role:", ["(none)"] + role_names,
                    default=cur.get("role", "(none)"),
                )
                if ans is BACK:
                    state = "pane_dir"; continue
                cur["role"], state = ans, "pane_prompt"

            elif state == "pane_prompt":
                pkey = self._pick_startup_prompt(cur.get("pkey"))
                if pkey is BACK:
                    state = "pane_role"; continue
                pcustom = cur.get("pcustom", "")
                if pkey == "custom":
                    typed = ask_text("Custom prompt (blank to go back):", default=pcustom)
                    if typed is None or not typed.strip():
                        cur["pkey"] = pkey
                        continue  # back to the prompt picker, keep selection
                    pcustom = typed
                cur["pkey"], cur["pcustom"], state = pkey, pcustom, "pane_more"

            elif state == "pane_more":
                # cur holds a finished-but-uncommitted pane.
                choice = ask_select_back(
                    "Pane set. Next?",
                    [
                        questionary.Choice("➕ Add another pane", "add"),
                        questionary.Choice("✓ Done — review & save", "done"),
                    ],
                )
                if choice is BACK:
                    state = "pane_prompt"; continue  # back to edit this pane
                panes.append(self._build_pane(cur))
                cur = {}
                state = "pane_dir" if choice == "add" else "review"

            elif state == "review":
                if not panes:
                    state = "pane_dir"; continue
                profile = Profile.new(name, layout, panes)
                console.print(self._review_table(profile))
                ans = ask_select(
                    "Profile ready:",
                    choices=[
                        questionary.Choice("Save and finish", "save"),
                        questionary.Choice("Add another pane", "add"),
                        questionary.Choice("Discard and return to menu", "discard"),
                    ],
                )
                if ans in (None, "discard"):
                    console.print("[yellow]Discarded.[/yellow]")
                    return
                if ans == "add":
                    state = "pane_dir"; continue
                self.profiles.save(profile)
                console.print(f"[green]Saved '{name}'.[/green]")
                return

    def delete_session(self) -> None:
        name = self._pick_profile("Delete which profile?")
        if not name:
            return
        if ask_confirm(f"Delete '{name}'?"):
            self.profiles.delete(name)
            console.print(f"[green]Deleted '{name}'.[/green]")
        else:
            console.print("[yellow]Nothing deleted.[/yellow]")

    def _roles_table(self, roles: list[Role]) -> Table:
        table = Table(title="Roles")
        table.add_column("Name"); table.add_column("Charter")
        for r in roles:
            charter = r.charter if len(r.charter) <= 60 else r.charter[:59] + "…"
            table.add_row(r.name, charter)
        return table

    def manage_roles(self) -> None:
        while True:
            roles = self.roles.load()
            console.print(self._roles_table(roles))
            action = ask_select(
                "Manage roles:",
                choices=["View a charter", "Edit a charter", "Back"],
            )
            if action in (None, "Back"):
                return
            if action == "View a charter":
                name = ask_select_back("View which role?", [r.name for r in roles])
                if name is BACK:
                    continue
                role = self.roles.get(name)
                console.print(Panel(role.charter, title=role.name, expand=False))
            elif action == "Edit a charter":
                name = ask_select_back("Edit which role?", [r.name for r in roles])
                if name is BACK:
                    continue
                current = self.roles.get(name)
                new_charter = questionary.text(
                    "Charter:", default=current.charter, multiline=True,
                    style=STYLE, qmark=MARK,
                ).ask()
                if new_charter is None or not new_charter.strip():
                    console.print("[yellow]No change.[/yellow]")
                    continue
                self.roles.upsert(Role(name, new_charter))
                console.print(f"[green]Updated '{name}'.[/green]")

    def _pick_profile(self, prompt: str) -> str | None:
        names = self.profiles.list()
        if not names:
            console.print("[yellow]No saved profiles yet.[/yellow]")
            return None
        ans = ask_select_back(prompt, names)
        return None if ans is BACK else ans

    def run(self) -> None:
        print_splash(console)
        actions = {
            "Launch session": self.launch_session,
            "Create session": self.create_session,
            "Dispatch from queue": self.dispatch_from_queue,
            "Delete session": self.delete_session,
            "Manage roles": self.manage_roles,
        }
        while True:
            choice = ask_select(
                "Claude Dispatch Hub", choices=list(actions) + ["Quit"]
            )
            if choice in (None, "Quit"):
                break
            actions[choice]()
