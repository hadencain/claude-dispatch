# Claude Dispatch Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows CLI launcher that turns a saved JSON profile into a live multi-agent Claude Code session in one Windows Terminal window.

**Architecture:** Three concentric layers, knowledge flows inward-out. Core (`models`, `launcher`, `validation`) is pure data + pure command construction with zero I/O dependencies beyond writing scripts and calling `subprocess`. Persistence (`store`, `roles`) handles JSON. Interface (`menu`, `main`) is the only layer allowed to call `questionary`/`rich`. The launch core (`launcher.py`) is built and proven first in isolation.

**Tech Stack:** Python 3.14, `rich`, `questionary`, Windows Terminal (`wt.exe`), PowerShell (`pwsh`), `claude` CLI, `pytest`.

## Global Constraints

- Python invoked as `python` (path `C:/Python314/python`); never `python3`.
- `launcher.py` MUST NOT import `menu`/`roles`, call `questionary`/`rich`, read JSON, or prompt. It receives a fully-resolved `Profile` + a `{role_name: charter}` dict.
- `store`/`roles` MUST NOT import `menu` or launch anything.
- Only `menu.py`/`main.py` may call `questionary` or `rich`.
- Subprocess launch uses an argument **list**, never `shell=True`.
- Layout → wt flag: `vertical` = `-H` (stacked rows), `horizontal` = `-V` (side-by-side columns), `grid` = computed `-V`/`-H` + `--size` + `move-focus` (best-effort).
- Per-profile JSON files at `config/profiles/<name>.json`; roles at `config/roles.json`; generated scripts in `config/.launch/`.
- Startup-prompt presets resolved to literal strings at save time. Presets: `continue` → "Continue development on this project.", `workspace` → "Check the workspace status for the current project.", `plan` → "/plan", `custom` → free text.
- TDD throughout: failing test → verify fail → minimal impl → verify pass → commit.

## File Structure

```
projecthub/
  CLAUDE.md                 # minimal project guide
  .gitignore                # venv/, __pycache__/, config/.launch/, config/profiles/, config/roles.json
  requirements.txt          # rich, questionary, pytest
  deps.md                   # dependency log
  dispatch_hub/
    __init__.py
    __main__.py             # python -m dispatch_hub -> main()
    models.py               # Role, Pane, Profile dataclasses + (de)serialization
    presets.py              # PRESETS constant map
    launcher.py             # MODULE A: command builder, script gen, launch
    roles.py                # DEFAULT_ROLES + RoleStore
    store.py                # ProfileStore
    validation.py           # path/tooling/name validation
    menu.py                 # interactive CLI (questionary + rich)
    main.py                 # entry: ensure config, seed roles, run menu
  tests/
    test_models.py
    test_launcher.py
    test_roles.py
    test_store.py
    test_validation.py
  docs/superpowers/specs/2026-06-21-claude-dispatch-hub-design.md
  docs/superpowers/plans/2026-06-21-claude-dispatch-hub.md
```

---

### Task 1: Project scaffold + git + test harness

**Files:**
- Create: `.gitignore`, `requirements.txt`, `deps.md`, `CLAUDE.md`, `dispatch_hub/__init__.py`, `tests/__init__.py`, `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: a runnable `pytest` harness and an importable `dispatch_hub` package.

- [ ] **Step 1: Initialize git and package dirs**

```bash
cd /c/Users/haden/documents/ship/src/projecthub
git init
mkdir -p dispatch_hub tests
```

- [ ] **Step 2: Create `.gitignore`**

```
venv/
__pycache__/
*.pyc
.pytest_cache/
config/.launch/
config/profiles/
config/roles.json
scratch/
```

- [ ] **Step 3: Create `requirements.txt`**

```
rich>=13
questionary>=2
pytest>=8
```

- [ ] **Step 4: Create `deps.md`**

```markdown
# Dependencies

| Package | Why |
|---------|-----|
| rich | Profile/role review tables and menu rendering |
| questionary | Arrow-key selection and prompts |
| pytest | Test runner (dev) |
```

- [ ] **Step 5: Create `CLAUDE.md`**

```markdown
# Claude Dispatch Hub

Windows CLI launcher for multi-agent Claude Code sessions via Windows Terminal.

- Run: `python -m dispatch_hub`
- Test: `python -m pytest tests/ -v`
- Spec: `docs/superpowers/specs/2026-06-21-claude-dispatch-hub-design.md`

`launcher.py` is the launch core — pure command construction, no I/O beyond writing scripts and `subprocess`. Do not import `menu`/`roles` into it.
```

- [ ] **Step 6: Create package + test init files**

`dispatch_hub/__init__.py`:
```python
"""Claude Dispatch Hub — multi-agent Claude Code session launcher."""
```
`tests/__init__.py`: (empty file)

- [ ] **Step 7: Write smoke test** — `tests/test_smoke.py`

```python
import dispatch_hub


def test_package_imports():
    assert dispatch_hub is not None
```

- [ ] **Step 8: Install deps and run**

```bash
python -m pip install -r requirements.txt
python -m pytest tests/ -v
```
Expected: 1 passed.

- [ ] **Step 9: Commit**

```bash
git add .gitignore requirements.txt deps.md CLAUDE.md dispatch_hub tests docs
git commit -m "chore: scaffold dispatch_hub package and test harness"
```

---

### Task 2: Data model (`models.py` + `presets.py`)

**Files:**
- Create: `dispatch_hub/models.py`, `dispatch_hub/presets.py`, `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Role(name: str, charter: str, builtin: bool = False)` with `.to_dict()` / `Role.from_dict(d)`.
  - `Pane(directory: str, role: str | None = None, startup_prompt: str = "", title: str | None = None)` with `.to_dict()` / `Pane.from_dict(d)`.
  - `Profile(name: str, layout: str, panes: list[Pane], created: str, modified: str)` with `.to_dict()` / `Profile.from_dict(d)` and `Profile.new(name, layout, panes)` classmethod that stamps `created`/`modified`.
  - `presets.PRESETS: dict[str, str | None]`.

- [ ] **Step 1: Write failing tests** — `tests/test_models.py`

```python
from dispatch_hub.models import Role, Pane, Profile
from dispatch_hub.presets import PRESETS


def test_role_roundtrip():
    r = Role(name="Backend", charter="Be backend.", builtin=True)
    assert Role.from_dict(r.to_dict()) == r


def test_pane_roundtrip_with_none_role():
    p = Pane(directory="C:/proj", role=None, startup_prompt="/plan")
    d = p.to_dict()
    assert d["role"] is None
    assert Pane.from_dict(d) == p


def test_profile_roundtrip_nested_panes():
    prof = Profile.new(
        "sprint", "horizontal",
        [Pane("C:/a", "Backend", "go"), Pane("C:/b", None, "/plan")],
    )
    back = Profile.from_dict(prof.to_dict())
    assert back == prof
    assert back.created and back.modified


def test_profile_new_stamps_timestamps():
    prof = Profile.new("x", "grid", [])
    assert prof.created == prof.modified


def test_presets_resolve_to_strings():
    assert PRESETS["plan"] == "/plan"
    assert PRESETS["custom"] is None
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL (ModuleNotFoundError: dispatch_hub.models).

- [ ] **Step 3: Implement `presets.py`**

```python
"""Startup-prompt presets, resolved to literal strings at save time."""

PRESETS: dict[str, str | None] = {
    "continue": "Continue development on this project.",
    "workspace": "Check the workspace status for the current project.",
    "plan": "/plan",
    "custom": None,
}
```

- [ ] **Step 4: Implement `models.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Role:
    name: str
    charter: str
    builtin: bool = False

    def to_dict(self) -> dict:
        return {"name": self.name, "charter": self.charter, "builtin": self.builtin}

    @classmethod
    def from_dict(cls, d: dict) -> "Role":
        return cls(name=d["name"], charter=d["charter"], builtin=d.get("builtin", False))


@dataclass
class Pane:
    directory: str
    role: str | None = None
    startup_prompt: str = ""
    title: str | None = None

    def to_dict(self) -> dict:
        return {
            "directory": self.directory,
            "role": self.role,
            "startup_prompt": self.startup_prompt,
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Pane":
        return cls(
            directory=d["directory"],
            role=d.get("role"),
            startup_prompt=d.get("startup_prompt", ""),
            title=d.get("title"),
        )


@dataclass
class Profile:
    name: str
    layout: str
    panes: list[Pane] = field(default_factory=list)
    created: str = ""
    modified: str = ""

    @classmethod
    def new(cls, name: str, layout: str, panes: list[Pane]) -> "Profile":
        ts = _now()
        return cls(name=name, layout=layout, panes=list(panes), created=ts, modified=ts)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "layout": self.layout,
            "panes": [p.to_dict() for p in self.panes],
            "created": self.created,
            "modified": self.modified,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        return cls(
            name=d["name"],
            layout=d["layout"],
            panes=[Pane.from_dict(p) for p in d.get("panes", [])],
            created=d.get("created", ""),
            modified=d.get("modified", ""),
        )
```

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest tests/test_models.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add dispatch_hub/models.py dispatch_hub/presets.py tests/test_models.py
git commit -m "feat: add Role/Pane/Profile data model and startup presets"
```

---

### Task 3: Launch core — command builder (`launcher.py`)

This is Module A. Pure, deterministic `wt.exe` argument-list construction. No terminal launched.

**Files:**
- Create: `dispatch_hub/launcher.py`, `tests/test_launcher.py`

**Interfaces:**
- Consumes: `models.Profile`, `models.Pane`.
- Produces:
  - `build_command(profile: Profile, script_paths: list[str]) -> list[str]` — full `wt.exe` arg list.
  - `_pane_title(pane: Pane) -> str` — `pane.title` or `pane.role` or directory basename.
  - `_layout_actions(layout: str, n: int) -> list[tuple[str, str | None, list[str]]]` — sequence of `("pane", flag_or_None, extra_flags)` and `("focus", direction, [])` actions.
  - Module constant `LAUNCH_DIR_NAME = ".launch"`.

- [ ] **Step 1: Write failing tests** — `tests/test_launcher.py`

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_launcher.py -v`
Expected: FAIL (cannot import build_command).

- [ ] **Step 3: Implement command builder in `launcher.py`**

```python
from __future__ import annotations

import math
import os

from .models import Pane, Profile

LAUNCH_DIR_NAME = ".launch"

# layout name -> wt split-pane divider flag for simple layouts
_SIMPLE_FLAG = {"vertical": "-H", "horizontal": "-V"}


def _pane_title(pane: Pane) -> str:
    if pane.title:
        return pane.title
    if pane.role:
        return pane.role
    base = os.path.basename(pane.directory.rstrip("/\\"))
    return base or pane.directory


def _grid_actions(n: int) -> list[tuple[str, str | None, list[str]]]:
    """Best-effort even grid. Pane count is exact; geometry is approximate
    and may need tuning during the live smoke test."""
    cols = math.ceil(math.sqrt(n))
    base, extra = divmod(n, cols)
    col_counts = [base + (1 if c < extra else 0) for c in range(cols)]

    actions: list[tuple[str, str | None, list[str]]] = [("pane", None, [])]
    # first pane of each subsequent column, left to right
    for c in range(1, cols):
        size = round(1.0 / (cols - c + 1), 3)
        actions.append(("pane", "-V", ["--size", str(size)]))
    # return focus to leftmost column
    for _ in range(cols - 1):
        actions.append(("focus", "left", []))
    # fill each column downward
    for c in range(cols):
        if c > 0:
            actions.append(("focus", "right", []))
        for r in range(col_counts[c] - 1):
            size = round(1.0 / (col_counts[c] - r), 3)
            actions.append(("pane", "-H", ["--size", str(size)]))
    return actions


def _layout_actions(layout: str, n: int) -> list[tuple[str, str | None, list[str]]]:
    if n <= 0:
        return []
    if layout == "grid":
        return _grid_actions(n)
    if layout not in _SIMPLE_FLAG:
        raise ValueError(f"unknown layout: {layout}")
    flag = _SIMPLE_FLAG[layout]
    actions: list[tuple[str, str | None, list[str]]] = [("pane", None, [])]
    for _ in range(n - 1):
        actions.append(("pane", flag, []))
    return actions


def build_command(profile: Profile, script_paths: list[str]) -> list[str]:
    actions = _layout_actions(profile.layout, len(profile.panes))
    subs: list[list[str]] = []
    pane_idx = 0
    for kind, flag, extra in actions:
        if kind == "focus":
            subs.append(["move-focus", flag or "left"])
            continue
        pane = profile.panes[pane_idx]
        script = script_paths[pane_idx]
        if pane_idx == 0:
            tokens = ["new-tab"]
        else:
            tokens = ["split-pane"] + ([flag] if flag else []) + list(extra)
        tokens += ["-d", pane.directory, "--title", _pane_title(pane),
                   "pwsh", "-NoExit", "-File", script]
        subs.append(tokens)
        pane_idx += 1

    cmd = ["wt.exe"]
    for j, sub in enumerate(subs):
        if j:
            cmd.append(";")
        cmd += sub
    return cmd
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_launcher.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add dispatch_hub/launcher.py tests/test_launcher.py
git commit -m "feat: wt.exe command builder for vertical/horizontal/grid layouts"
```

---

### Task 4: Launch core — script generation + launch (`launcher.py`)

**Files:**
- Modify: `dispatch_hub/launcher.py`
- Modify: `tests/test_launcher.py`

**Interfaces:**
- Consumes: `build_command`, `models.Profile`, `models.Pane`.
- Produces:
  - `render_pane_script(pane: Pane, charter: str | None) -> str` — PowerShell script text (CRLF). Self-deletes, `Set-Location`, runs `claude` with optional `--append-system-prompt`.
  - `write_pane_scripts(profile: Profile, charters: dict[str, str], work_dir: Path) -> list[Path]`.
  - `sweep_stale_scripts(work_dir: Path) -> None`.
  - `launch(profile: Profile, charters: dict[str, str], work_dir: Path, runner=subprocess.run)` — sweeps, writes, builds, runs; returns runner result.

- [ ] **Step 1: Write failing tests** — append to `tests/test_launcher.py`

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_launcher.py -v`
Expected: FAIL (cannot import render_pane_script).

- [ ] **Step 3: Implement script generation + launch** — append to `dispatch_hub/launcher.py`

```python
import re
import subprocess
from pathlib import Path


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name) or "profile"


def render_pane_script(pane: Pane, charter: str | None) -> str:
    dir_lit = pane.directory.replace("'", "''")
    lines = [
        "Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue",
        f"Set-Location -LiteralPath '{dir_lit}'",
    ]
    has_prompt = bool(pane.startup_prompt)
    if has_prompt:
        lines += ["$prompt = @'", pane.startup_prompt, "'@"]
    if charter is not None:
        lines += ["$charter = @'", charter, "'@"]

    call = "claude"
    if charter is not None:
        call += " --append-system-prompt $charter"
    if has_prompt:
        call += " $prompt"
    lines.append(call)
    return "\r\n".join(lines) + "\r\n"


def write_pane_scripts(profile: Profile, charters: dict[str, str],
                       work_dir: Path) -> list[Path]:
    work_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    safe = _safe_name(profile.name)
    for i, pane in enumerate(profile.panes):
        charter = charters.get(pane.role) if pane.role else None
        content = render_pane_script(pane, charter)
        p = work_dir / f"{safe}_{i}.ps1"
        p.write_text(content, encoding="utf-8")
        paths.append(p)
    return paths


def sweep_stale_scripts(work_dir: Path) -> None:
    if not work_dir.exists():
        return
    for f in work_dir.glob("*.ps1"):
        try:
            f.unlink()
        except OSError:
            pass


def launch(profile: Profile, charters: dict[str, str], work_dir: Path,
           runner=subprocess.run):
    sweep_stale_scripts(work_dir)
    paths = write_pane_scripts(profile, charters, work_dir)
    cmd = build_command(profile, [str(p) for p in paths])
    return runner(cmd)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_launcher.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add dispatch_hub/launcher.py tests/test_launcher.py
git commit -m "feat: per-pane PowerShell script generation and launch orchestration"
```

---

### Task 5: Roles (`roles.py`)

**Files:**
- Create: `dispatch_hub/roles.py`, `tests/test_roles.py`

**Interfaces:**
- Consumes: `models.Role`.
- Produces:
  - `DEFAULT_ROLES: list[Role]` — Architect, Backend, Frontend, QA (`builtin=True`).
  - `RoleStore(path: Path)` with: `ensure_seeded()`, `load() -> list[Role]`, `save(roles: list[Role])`, `get(name) -> Role | None`, `charters() -> dict[str, str]`, `upsert(role: Role)`, `delete(name: str)`.

- [ ] **Step 1: Write failing tests** — `tests/test_roles.py`

```python
from dispatch_hub.roles import RoleStore, DEFAULT_ROLES
from dispatch_hub.models import Role


def test_default_roles_present():
    names = {r.name for r in DEFAULT_ROLES}
    assert names == {"Architect", "Backend", "Frontend", "QA"}
    assert all(r.builtin and r.charter for r in DEFAULT_ROLES)


def test_ensure_seeded_writes_defaults(tmp_path):
    store = RoleStore(tmp_path / "roles.json")
    store.ensure_seeded()
    assert (tmp_path / "roles.json").exists()
    assert {r.name for r in store.load()} == {"Architect", "Backend", "Frontend", "QA"}


def test_ensure_seeded_is_idempotent_and_preserves_edits(tmp_path):
    store = RoleStore(tmp_path / "roles.json")
    store.ensure_seeded()
    store.upsert(Role("Backend", "edited charter", builtin=True))
    store.ensure_seeded()  # must not overwrite
    assert store.get("Backend").charter == "edited charter"


def test_charters_returns_name_to_charter_map(tmp_path):
    store = RoleStore(tmp_path / "roles.json")
    store.ensure_seeded()
    c = store.charters()
    assert c["Architect"] == store.get("Architect").charter


def test_upsert_adds_then_delete_removes(tmp_path):
    store = RoleStore(tmp_path / "roles.json")
    store.ensure_seeded()
    store.upsert(Role("Docs", "write docs"))
    assert store.get("Docs").charter == "write docs"
    store.delete("Docs")
    assert store.get("Docs") is None
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_roles.py -v`
Expected: FAIL (cannot import RoleStore).

- [ ] **Step 3: Implement `roles.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

from .models import Role

DEFAULT_ROLES: list[Role] = [
    Role("Architect",
         "You are the Architect. Focus on system design, module boundaries, "
         "interfaces, and trade-offs. Propose structure and review designs; do not "
         "write implementation code unless explicitly asked. Push back on premature "
         "complexity and call out where boundaries are unclear.",
         builtin=True),
    Role("Backend",
         "You are the Backend engineer. Focus on data models, business logic, APIs, "
         "persistence, and their tests. Implement server-side and core logic. Defer UI "
         "and styling to the Frontend role and large-scale structure to the Architect.",
         builtin=True),
    Role("Frontend",
         "You are the Frontend engineer. Focus on UI, components, layout, state "
         "management, and user-facing behavior. Implement and refine the interface. "
         "Defer data-model and server-logic decisions to the Backend role.",
         builtin=True),
    Role("QA",
         "You are QA. Focus on testing, edge cases, regressions, and verification. "
         "Write and run tests, reproduce bugs, and report findings precisely with steps "
         "to reproduce. Do not implement features; verify them and surface gaps.",
         builtin=True),
]


class RoleStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def ensure_seeded(self) -> None:
        if not self.path.exists():
            self.save(DEFAULT_ROLES)

    def load(self) -> list[Role]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return [Role.from_dict(d) for d in data]

    def save(self, roles: list[Role]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([r.to_dict() for r in roles], indent=2), encoding="utf-8"
        )

    def get(self, name: str) -> Role | None:
        for r in self.load():
            if r.name == name:
                return r
        return None

    def charters(self) -> dict[str, str]:
        return {r.name: r.charter for r in self.load()}

    def upsert(self, role: Role) -> None:
        roles = self.load()
        for i, r in enumerate(roles):
            if r.name == role.name:
                roles[i] = role
                break
        else:
            roles.append(role)
        self.save(roles)

    def delete(self, name: str) -> None:
        self.save([r for r in self.load() if r.name != name])
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_roles.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add dispatch_hub/roles.py tests/test_roles.py
git commit -m "feat: built-in role charters and RoleStore CRUD"
```

---

### Task 6: Profile persistence (`store.py`)

**Files:**
- Create: `dispatch_hub/store.py`, `tests/test_store.py`

**Interfaces:**
- Consumes: `models.Profile`.
- Produces:
  - `ProfileStore(directory: Path)` with: `path_for(name) -> Path`, `save(profile)`, `load(name) -> Profile`, `delete(name)`, `list() -> list[str]` (sorted names, corrupt files skipped with a warning to stderr).

- [ ] **Step 1: Write failing tests** — `tests/test_store.py`

```python
from dispatch_hub.store import ProfileStore
from dispatch_hub.models import Profile, Pane


def test_save_then_load_roundtrip(tmp_path):
    store = ProfileStore(tmp_path)
    prof = Profile.new("sprint", "grid", [Pane("C:/a", "Backend", "go")])
    store.save(prof)
    assert store.load("sprint") == prof


def test_save_writes_one_file_per_profile(tmp_path):
    store = ProfileStore(tmp_path)
    store.save(Profile.new("a", "vertical", []))
    store.save(Profile.new("b", "horizontal", []))
    assert (tmp_path / "a.json").exists()
    assert (tmp_path / "b.json").exists()


def test_list_sorted_and_skips_corrupt(tmp_path, capsys):
    store = ProfileStore(tmp_path)
    store.save(Profile.new("zeta", "grid", []))
    store.save(Profile.new("alpha", "grid", []))
    (tmp_path / "broken.json").write_text("{ not json")
    names = store.list()
    assert names == ["alpha", "zeta"]          # corrupt skipped, sorted
    assert "broken" in capsys.readouterr().err  # warning emitted


def test_delete_removes_file(tmp_path):
    store = ProfileStore(tmp_path)
    store.save(Profile.new("temp", "grid", []))
    store.delete("temp")
    assert not (tmp_path / "temp.json").exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_store.py -v`
Expected: FAIL (cannot import ProfileStore).

- [ ] **Step 3: Implement `store.py`**

```python
from __future__ import annotations

import json
import sys
from pathlib import Path

from .models import Profile


class ProfileStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def path_for(self, name: str) -> Path:
        return self.directory / f"{name}.json"

    def save(self, profile: Profile) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path_for(profile.name).write_text(
            json.dumps(profile.to_dict(), indent=2), encoding="utf-8"
        )

    def load(self, name: str) -> Profile:
        data = json.loads(self.path_for(name).read_text(encoding="utf-8"))
        return Profile.from_dict(data)

    def delete(self, name: str) -> None:
        self.path_for(name).unlink(missing_ok=True)

    def list(self) -> list[str]:
        if not self.directory.exists():
            return []
        names: list[str] = []
        for f in sorted(self.directory.glob("*.json")):
            try:
                json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                print(f"warning: skipping corrupt profile '{f.stem}'", file=sys.stderr)
                continue
            names.append(f.stem)
        return names
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_store.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add dispatch_hub/store.py tests/test_store.py
git commit -m "feat: per-file profile persistence with corrupt-file skip"
```

---

### Task 7: Validation (`validation.py`)

**Files:**
- Create: `dispatch_hub/validation.py`, `tests/test_validation.py`

**Interfaces:**
- Consumes: `models.Profile`.
- Produces:
  - `validate_directories(profile: Profile) -> list[str]` — returns missing/invalid directories (empty list = all valid).
  - `check_tooling(which=shutil.which) -> list[str]` — returns missing tools among `wt.exe`, `claude`.
  - `validate_profile_name(name: str, existing: list[str]) -> str | None` — returns an error message or `None` if valid.

- [ ] **Step 1: Write failing tests** — `tests/test_validation.py`

```python
from dispatch_hub.validation import (
    validate_directories, check_tooling, validate_profile_name,
)
from dispatch_hub.models import Profile, Pane


def test_validate_directories_flags_missing(tmp_path):
    good = str(tmp_path)
    prof = Profile.new("p", "grid", [Pane(good, None, ""), Pane("C:/nope_xyz", None, "")])
    missing = validate_directories(prof)
    assert missing == ["C:/nope_xyz"]


def test_validate_directories_all_present(tmp_path):
    prof = Profile.new("p", "grid", [Pane(str(tmp_path), None, "")])
    assert validate_directories(prof) == []


def test_check_tooling_reports_missing_claude():
    def fake_which(name):
        return "C:/wt.exe" if name == "wt.exe" else None
    assert check_tooling(which=fake_which) == ["claude"]


def test_check_tooling_all_present():
    assert check_tooling(which=lambda n: "found") == []


def test_validate_profile_name_rules():
    assert validate_profile_name("", []) is not None          # empty
    assert validate_profile_name("a/b", []) is not None       # unsafe char
    assert validate_profile_name("dup", ["dup"]) is not None  # collision
    assert validate_profile_name("ok-name_1", ["other"]) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_validation.py -v`
Expected: FAIL (cannot import validation).

- [ ] **Step 3: Implement `validation.py`**

```python
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
    return [tool for tool in REQUIRED_TOOLS if which(tool) is None]


def validate_profile_name(name: str, existing: list[str]) -> str | None:
    if not name or not name.strip():
        return "Profile name cannot be empty."
    if not _SAFE_NAME.match(name):
        return "Use only letters, digits, dot, dash, underscore (no spaces or slashes)."
    if name in existing:
        return f"A profile named '{name}' already exists."
    return None
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_validation.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add dispatch_hub/validation.py tests/test_validation.py
git commit -m "feat: directory, tooling, and profile-name validation"
```

---

### Task 8: Interactive menu + entry point (`menu.py`, `main.py`, `__main__.py`)

The interface layer. `questionary`/`rich` flows are exercised manually; the one pure helper (`resolve_startup_prompt`) is unit-tested.

**Files:**
- Create: `dispatch_hub/menu.py`, `dispatch_hub/main.py`, `dispatch_hub/__main__.py`
- Modify: `tests/test_models.py` is unaffected; add `tests/test_menu.py`

**Interfaces:**
- Consumes: `ProfileStore`, `RoleStore`, `validate_directories`, `check_tooling`, `validate_profile_name`, `launcher.launch`, `presets.PRESETS`.
- Produces:
  - `resolve_startup_prompt(choice: str, custom_text: str = "") -> str` — maps a preset key (or `"custom"`) to its literal string.
  - `CONFIG_DIR`, `PROFILES_DIR`, `ROLES_FILE`, `LAUNCH_DIR` path constants rooted at `config/`.
  - `App` class wiring the stores; `run()` runs the menu loop.
  - `main()` in `main.py` — ensures config dirs exist, seeds roles, starts `App.run()`.

- [ ] **Step 1: Write failing test** — `tests/test_menu.py`

```python
from dispatch_hub.menu import resolve_startup_prompt


def test_resolve_preset_returns_literal():
    assert resolve_startup_prompt("plan") == "/plan"
    assert resolve_startup_prompt("continue") == "Continue development on this project."


def test_resolve_custom_returns_user_text():
    assert resolve_startup_prompt("custom", "do the thing") == "do the thing"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_menu.py -v`
Expected: FAIL (cannot import resolve_startup_prompt).

- [ ] **Step 3: Implement `menu.py`**

```python
from __future__ import annotations

from pathlib import Path

import questionary
from rich.console import Console
from rich.table import Table

from .launcher import LAUNCH_DIR_NAME, launch
from .models import Pane, Profile
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
        panes: list[Pane] = []
        role_names = [r.name for r in self.roles.load()]
        while True:
            directory = questionary.text("Project directory:").ask()
            role = questionary.select(
                "Role:", choices=["(none)"] + role_names
            ).ask()
            role = None if role == "(none)" else role
            choice = questionary.select(
                "Startup prompt:",
                choices=["continue", "workspace", "plan", "custom"],
            ).ask()
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

    def manage_roles(self) -> None:
        roles = self.roles.load()
        table = Table(title="Roles")
        table.add_column("Name"); table.add_column("Built-in"); table.add_column("Charter")
        for r in roles:
            table.add_row(r.name, "yes" if r.builtin else "no", r.charter[:60] + "…")
        console.print(table)
        # editing flow intentionally minimal for v1; full editor is future work
        console.print("[dim]Edit config/roles.json directly to change charters.[/dim]")

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
```

- [ ] **Step 4: Implement `main.py`**

```python
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
```

- [ ] **Step 5: Implement `__main__.py`**

```python
from .main import main

main()
```

- [ ] **Step 6: Run unit tests + full suite**

Run: `python -m pytest tests/ -v`
Expected: all tests pass (models 5, launcher 11, roles 5, store 4, validation 5, menu 2).

- [ ] **Step 7: Commit**

```bash
git add dispatch_hub/menu.py dispatch_hub/main.py dispatch_hub/__main__.py tests/test_menu.py
git commit -m "feat: interactive menu, create/launch/delete flows, entry point"
```

- [ ] **Step 8: Live smoke test (manual — reported, not auto-completed)**

1. Run `python -m dispatch_hub`.
2. Create a profile: two real directories, layout `horizontal`, one Backend role, one `(none)` role, startup prompts `continue` and `plan`.
3. Launch it. Confirm: one Windows Terminal window opens, split into two side-by-side panes, each in the correct directory, each running `claude`; the Backend pane reflects its charter; `config/.launch/` has no leftover `.ps1` after the panes start.
4. Repeat with `vertical` (stacked) and `grid` (≥3 panes). Tune `_grid_actions` sizing/focus if the grid is visibly uneven — geometry is best-effort per the spec.

Report results as "builds + unit-tested + command verified, needs live confirmation" until step 8 is observed passing.

---

## Self-Review

**Spec coverage:**
- Workspace profiles, create/save/load/delete → Tasks 2, 6, 8. ✓
- Number of terminals / project dirs / layout → `Profile.panes` + `layout`, Tasks 2/3. ✓
- Launch Windows Terminal, cd + launch Claude per pane → Tasks 3/4. ✓
- Session save/load, JSON storage → Task 6. ✓
- Interactive CLI menu (create/launch/save/delete) → Task 8. ✓
- Validate project paths → Task 7 (+ enforced at launch in Task 8). ✓
- Agent roles (Architect/Backend/Frontend/QA), per project, editable defaults → Task 5; applied via `--append-system-prompt` in Task 4. ✓
- Startup prompt presets + custom → `presets.py` Task 2, resolved in Task 8. ✓
- Modular, layered, launcher isolated → enforced by Global Constraints; launcher has no interface imports. ✓
- Self-deleting scripts + stale sweep → Task 4. ✓
- Grid best-effort, vertical/horizontal exact → Task 3. ✓

**Placeholder scan:** No "TBD"/"implement later". `manage_roles` is intentionally scoped to read + point at the JSON file for v1 (full charter editor is explicitly future work, not a placeholder gap) — charters remain editable on disk, satisfying the "editable defaults" requirement.

**Type consistency:** `build_command(profile, script_paths)`, `launch(profile, charters, work_dir, runner)`, `RoleStore.charters() -> dict[str,str]`, `validate_directories -> list[str]`, `check_tooling(which=...) -> list[str]`, `resolve_startup_prompt(choice, custom_text)` — names and signatures match across all tasks and the menu's call sites.
