# Work Queue Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Dispatch from queue" menu action that reads an Obsidian work-queue markdown file, uses the Anthropic API to assign each selected item a role + project directory + expanded startup prompt, then launches a tiled Claude Code session and moves dispatched items to `## In Progress`.

**Architecture:** Three new pure-ish modules join the package — `queue.py` (stdlib-only markdown parse/move), `anthropic_client.py` (the only module importing the SDK), `triage.py` (one batched classification call, output constrained not trusted). `menu.py` wires them and owns all config I/O and prompting. `launcher.py` is untouched and imports none of them. Spec: `docs/superpowers/specs/2026-06-24-work-queue-dispatch-design.md`.

**Tech Stack:** Python 3.14 (`C:/Python314/python`), `questionary`, `rich`, `pytest`, new dep `anthropic`.

## Global Constraints

- Python interpreter is `python` (maps to `C:/Python314/python`); never `python3`.
- Run tests with `python -m pytest tests/ -v` from the project root `C:/Users/haden/Documents/Ship/src/claude-dispatch`.
- `launcher.py` must not import `queue`, `triage`, `anthropic_client`, `menu`, or `roles`.
- `queue.py` imports standard library only — no `anthropic`, no `triage`, no TUI, no network.
- `anthropic_client.py` is the only module that imports `anthropic`; the import is lazy (inside the method that calls the SDK) so the package imports without the SDK installed and tests run offline.
- `triage.py` must not import `menu`, `questionary`, or `rich`.
- Commit messages: body only, no `Co-Authored-By` or any AI-attribution trailer.
- All new files start with `from __future__ import annotations` to match the codebase.
- Default triage model string is exactly `claude-sonnet-4-6`.
- The unknown/no-role sentinel string is exactly `(none)` (matches `menu.py`'s existing `_build_pane`).
- Work is on branch `feat/work-queue-dispatch` (already created; the spec commit is on it).

---

### Task 1: `queue.py` — parse and move work-queue markdown

**Files:**
- Create: `dispatch_hub/queue.py`
- Test: `tests/test_queue.py`

**Interfaces:**
- Consumes: nothing (stdlib only).
- Produces:
  - `QueuedItem` — frozen dataclass with fields `raw: str` (the full original line) and `text: str` (bullet text, leading `- ` stripped and whitespace-trimmed).
  - `read_queued(text: str) -> list[QueuedItem]` — bullets under the `## Queued` section only.
  - `move_to_in_progress(text: str, raw_lines: list[str], today: str) -> str` — returns new file text with each matched raw line removed from `## Queued` and inserted (dated ` (dispatched <today>)`) at the top of `## In Progress`. Unmatched lines are left in place.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_queue.py
from dispatch_hub.queue import QueuedItem, read_queued, move_to_in_progress

SAMPLE = (
    "## Queued\n"
    "\n"
    "- claude-dispatch  creating new repos\n"
    "- voice formant replicator/visualizer\n"
    "\n"
    "## In Progress\n"
    "\n"
    "- Senses: port senses-audio (started 2026-06-24)\n"
    "\n"
    "## Done\n"
    "\n"
    "- old finished thing\n"
)


def test_read_queued_returns_only_queued_bullets():
    items = read_queued(SAMPLE)
    assert [i.text for i in items] == [
        "claude-dispatch  creating new repos",
        "voice formant replicator/visualizer",
    ]
    # raw preserves the full original line for later exact-match moves
    assert items[0].raw == "- claude-dispatch  creating new repos"


def test_read_queued_ignores_in_progress_and_done():
    items = read_queued(SAMPLE)
    texts = [i.text for i in items]
    assert "old finished thing" not in texts
    assert all("Senses" not in t for t in texts)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_queue.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dispatch_hub.queue'`

- [ ] **Step 3: Write minimal implementation of parsing**

```python
# dispatch_hub/queue.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueuedItem:
    raw: str
    text: str


def _section_of(line: str, current: str | None) -> str | None:
    """Return the section name a header line opens, else the unchanged current."""
    s = line.strip()
    if s.startswith("## "):
        return s[3:].strip().lower()
    return current


def read_queued(text: str) -> list[QueuedItem]:
    items: list[QueuedItem] = []
    current: str | None = None
    for line in text.splitlines():
        current = _section_of(line, current)
        if line.strip().startswith("## "):
            continue
        if current == "queued" and line.lstrip().startswith("- "):
            bullet = line.strip()[2:].strip()
            items.append(QueuedItem(raw=line, text=bullet))
    return items
```

- [ ] **Step 4: Run test to verify parsing passes**

Run: `python -m pytest tests/test_queue.py -v`
Expected: PASS (both parse tests)

- [ ] **Step 5: Write the failing move test**

```python
# append to tests/test_queue.py
def test_move_to_in_progress_relocates_and_dates_line():
    raw = "- voice formant replicator/visualizer"
    out = move_to_in_progress(SAMPLE, [raw], "2026-06-24")
    # gone from Queued
    assert "- voice formant replicator/visualizer\n" not in out.split("## In Progress")[0]
    # present and dated at top of In Progress
    in_progress = out.split("## In Progress")[1].split("## Done")[0]
    assert "- voice formant replicator/visualizer (dispatched 2026-06-24)" in in_progress


def test_move_to_in_progress_preserves_done_and_untouched_bullets():
    out = move_to_in_progress(SAMPLE, ["- voice formant replicator/visualizer"], "2026-06-24")
    # Done section byte-identical
    assert out.split("## Done")[1] == SAMPLE.split("## Done")[1]
    # the other queued bullet still under Queued, unchanged
    queued = out.split("## In Progress")[0]
    assert "- claude-dispatch  creating new repos\n" in queued


def test_move_to_in_progress_skips_unmatched_line():
    out = move_to_in_progress(SAMPLE, ["- not in the file"], "2026-06-24")
    assert out == SAMPLE  # nothing matched => nothing changed
```

- [ ] **Step 6: Run move test to verify it fails**

Run: `python -m pytest tests/test_queue.py -v`
Expected: FAIL with `ImportError: cannot import name 'move_to_in_progress'`

- [ ] **Step 7: Implement `move_to_in_progress`**

```python
# append to dispatch_hub/queue.py
def move_to_in_progress(text: str, raw_lines: list[str], today: str) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    targets = set(raw_lines)
    lines = text.splitlines()

    moved: list[str] = []
    kept: list[str] = []
    current: str | None = None
    for line in lines:
        current = _section_of(line, current)
        if current == "queued" and not line.strip().startswith("## ") and line in targets:
            moved.append(f"{line} (dispatched {today})")
            continue
        kept.append(line)

    if not moved:
        return text  # nothing matched; do not rewrite, preserve bytes exactly

    out: list[str] = []
    inserted = False
    for line in kept:
        out.append(line)
        if not inserted and line.strip().lower() == "## in progress":
            out.extend(moved)
            inserted = True
    if not inserted:  # no In Progress header present; create one at the end
        out += ["", "## In Progress", *moved]

    result = newline.join(out)
    if text.endswith("\n"):
        result += newline
    return result
```

- [ ] **Step 8: Run the full queue test file**

Run: `python -m pytest tests/test_queue.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 9: Commit**

```bash
git add dispatch_hub/queue.py tests/test_queue.py
git commit -m "feat: work-queue markdown parse and move-to-in-progress"
```

---

### Task 2: `anthropic_client.py` — key resolution + thin SDK wrapper

**Files:**
- Create: `dispatch_hub/anthropic_client.py`
- Modify: `requirements.txt`
- Test: `tests/test_anthropic_client.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `NoApiKey(RuntimeError)` — raised when no key resolves.
  - `resolve_api_key(settings: dict, environ=os.environ) -> str` — returns `ANTHROPIC_API_KEY` env value if set and non-empty, else `settings["anthropic_api_key"]` if present and non-empty, else raises `NoApiKey`.
  - `TriageClient` — `__init__(self, api_key: str, model: str)`; `complete(self, system: str, user: str) -> str` returns the model's text response. The `anthropic` import is lazy inside `complete`.

- [ ] **Step 1: Write the failing key-resolution test**

```python
# tests/test_anthropic_client.py
import pytest
from dispatch_hub.anthropic_client import resolve_api_key, NoApiKey


def test_env_var_takes_precedence():
    env = {"ANTHROPIC_API_KEY": "env-key"}
    assert resolve_api_key({"anthropic_api_key": "settings-key"}, environ=env) == "env-key"


def test_falls_back_to_settings_key():
    assert resolve_api_key({"anthropic_api_key": "settings-key"}, environ={}) == "settings-key"


def test_raises_when_no_key_anywhere():
    with pytest.raises(NoApiKey):
        resolve_api_key({}, environ={})


def test_blank_env_value_is_ignored():
    env = {"ANTHROPIC_API_KEY": ""}
    assert resolve_api_key({"anthropic_api_key": "settings-key"}, environ=env) == "settings-key"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_anthropic_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dispatch_hub.anthropic_client'`

- [ ] **Step 3: Implement key resolution and the client shell**

```python
# dispatch_hub/anthropic_client.py
from __future__ import annotations

import os

_ENV_KEY = "ANTHROPIC_API_KEY"


class NoApiKey(RuntimeError):
    """No Anthropic API key could be resolved from env or settings."""


def resolve_api_key(settings: dict, environ=os.environ) -> str:
    env_val = (environ.get(_ENV_KEY) or "").strip()
    if env_val:
        return env_val
    settings_val = (settings.get("anthropic_api_key") or "").strip()
    if settings_val:
        return settings_val
    raise NoApiKey(
        f"No Anthropic API key. Set the {_ENV_KEY} environment variable, "
        "or add 'anthropic_api_key' to config/settings.json."
    )


class TriageClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def complete(self, system: str, user: str) -> str:
        from anthropic import Anthropic  # lazy: keeps the package importable without the SDK

        client = Anthropic(api_key=self.api_key)
        msg = client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in msg.content if getattr(block, "type", None) == "text")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_anthropic_client.py -v`
Expected: PASS (4 tests; `complete` is not exercised here — no network)

- [ ] **Step 5: Add the dependency**

Edit `requirements.txt` to append one line so it reads:

```
rich>=13
questionary>=2
pytest>=8
anthropic>=0.40
```

- [ ] **Step 6: Commit**

```bash
git add dispatch_hub/anthropic_client.py tests/test_anthropic_client.py requirements.txt
git commit -m "feat: anthropic key resolution and thin triage client"
```

---

### Task 3: `triage.py` — batched classification, output constrained

**Files:**
- Create: `dispatch_hub/triage.py`
- Test: `tests/test_triage.py`

**Interfaces:**
- Consumes: `TriageClient`-shaped object exposing `complete(system: str, user: str) -> str` (injected; tests pass a fake).
- Produces:
  - `DEFAULT_MODEL = "claude-sonnet-4-6"`, `NONE_ROLE = "(none)"`.
  - `Proposal` — dataclass: `item_index: int`, `item_text: str`, `role: str | None`, `directory: str`, `startup_prompt: str`, `reason: str`, `unresolved: bool`.
  - `build_user_payload(items: list[str], role_names: list[str], directories: list[str]) -> str` — JSON string sent to the model.
  - `parse_response(text: str, items: list[str], role_names: list[str], directories: list[str]) -> list[Proposal]` — pure; clamps role to a known name or `None`, marks `unresolved` when directory is not in `directories`, falls back `startup_prompt` to the item text when blank.
  - `classify(items, role_names, directories, client) -> list[Proposal]` — builds payload, calls `client.complete`, parses; on JSON failure retries once, then raises `ValueError`.

- [ ] **Step 1: Write the failing parse test**

```python
# tests/test_triage.py
import json
import pytest
from dispatch_hub.triage import (
    Proposal, parse_response, classify, build_user_payload, NONE_ROLE,
)

ITEMS = ["fix spotter pipeline", "make a distortion plugin"]
ROLES = ["Backend", "QA", "Research"]
DIRS = ["C:/ship/spotter", "C:/ship/distortion"]


def _canned(role0, dir0):
    return json.dumps([
        {"item_index": 0, "role": role0, "directory": dir0,
         "startup_prompt": "Check whether the spotter pipeline finished on the new fixes.",
         "reason": "ops check"},
        {"item_index": 1, "role": "Backend", "directory": "C:/ship/distortion",
         "startup_prompt": "", "reason": "build it"},
    ])


def test_parse_maps_fields_and_clamps_known_role():
    props = parse_response(_canned("QA", "C:/ship/spotter"), ITEMS, ROLES, DIRS)
    assert props[0].role == "QA"
    assert props[0].directory == "C:/ship/spotter"
    assert props[0].unresolved is False


def test_parse_unknown_role_becomes_none():
    props = parse_response(_canned("Wizard", "C:/ship/spotter"), ITEMS, ROLES, DIRS)
    assert props[0].role is None


def test_parse_unknown_directory_flags_unresolved():
    props = parse_response(_canned("QA", "C:/nope"), ITEMS, ROLES, DIRS)
    assert props[0].unresolved is True


def test_parse_blank_prompt_falls_back_to_item_text():
    props = parse_response(_canned("QA", "C:/ship/spotter"), ITEMS, ROLES, DIRS)
    assert props[1].startup_prompt == "make a distortion plugin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_triage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dispatch_hub.triage'`

- [ ] **Step 3: Implement payload + parse**

```python
# dispatch_hub/triage.py
from __future__ import annotations

import json
from dataclasses import dataclass

DEFAULT_MODEL = "claude-sonnet-4-6"
NONE_ROLE = "(none)"

SYSTEM_PROMPT = (
    "You assign software work items to a role, a project directory, and a concrete "
    "startup prompt for a coding agent. You are given a list of items (each with an "
    "index), a list of allowed role names, and a list of allowed project directories. "
    "For every item return one object. 'role' MUST be exactly one of the allowed role "
    "names, or the string '(none)' if none fit. 'directory' MUST be exactly one of the "
    "allowed directories. 'startup_prompt' is a clear first instruction for the agent, "
    "expanded from the terse item into something actionable. 'reason' is one short "
    "phrase. Respond with ONLY a JSON array of objects with keys: item_index, role, "
    "directory, startup_prompt, reason. No prose, no markdown fences."
)


@dataclass
class Proposal:
    item_index: int
    item_text: str
    role: str | None
    directory: str
    startup_prompt: str
    reason: str
    unresolved: bool


def build_user_payload(items: list[str], role_names: list[str], directories: list[str]) -> str:
    return json.dumps({
        "items": [{"index": i, "text": t} for i, t in enumerate(items)],
        "allowed_roles": role_names,
        "allowed_directories": directories,
    }, indent=2)


def _strip_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s[: s.rfind("```")]
    return s.strip()


def parse_response(text: str, items: list[str], role_names: list[str],
                   directories: list[str]) -> list[Proposal]:
    data = json.loads(_strip_fences(text))
    dir_set = set(directories)
    role_set = set(role_names)
    props: list[Proposal] = []
    for obj in data:
        idx = int(obj["item_index"])
        item_text = items[idx]
        raw_role = obj.get("role")
        role = raw_role if raw_role in role_set else None
        directory = obj.get("directory", "")
        prompt = (obj.get("startup_prompt") or "").strip() or item_text
        props.append(Proposal(
            item_index=idx,
            item_text=item_text,
            role=role,
            directory=directory,
            startup_prompt=prompt,
            reason=obj.get("reason", ""),
            unresolved=directory not in dir_set,
        ))
    props.sort(key=lambda p: p.item_index)
    return props
```

- [ ] **Step 4: Run parse tests to verify they pass**

Run: `python -m pytest tests/test_triage.py -v`
Expected: PASS (4 parse tests)

- [ ] **Step 5: Write the failing classify (retry + raise) test**

```python
# append to tests/test_triage.py
class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def complete(self, system, user):
        self.calls += 1
        return self._responses.pop(0)


def test_classify_happy_path_single_call():
    client = _FakeClient([_canned("QA", "C:/ship/spotter")])
    props = classify(ITEMS, ROLES, DIRS, client)
    assert client.calls == 1
    assert len(props) == 2


def test_classify_retries_once_then_succeeds():
    client = _FakeClient(["not json at all", _canned("QA", "C:/ship/spotter")])
    props = classify(ITEMS, ROLES, DIRS, client)
    assert client.calls == 2
    assert len(props) == 2


def test_classify_raises_after_second_bad_response():
    client = _FakeClient(["nope", "still nope"])
    with pytest.raises(ValueError):
        classify(ITEMS, ROLES, DIRS, client)
    assert client.calls == 2
```

- [ ] **Step 6: Run to verify failure**

Run: `python -m pytest tests/test_triage.py -v`
Expected: FAIL with `ImportError: cannot import name 'classify'`

- [ ] **Step 7: Implement `classify`**

```python
# append to dispatch_hub/triage.py
def classify(items: list[str], role_names: list[str], directories: list[str],
             client) -> list[Proposal]:
    payload = build_user_payload(items, role_names, directories)
    last_error: Exception | None = None
    for _ in range(2):  # one initial attempt + one retry
        text = client.complete(SYSTEM_PROMPT, payload)
        try:
            return parse_response(text, items, role_names, directories)
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            last_error = exc
    raise ValueError(f"Triage returned unparseable output: {last_error}")
```

- [ ] **Step 8: Run the full triage test file**

Run: `python -m pytest tests/test_triage.py -v`
Expected: PASS (7 tests)

- [ ] **Step 9: Commit**

```bash
git add dispatch_hub/triage.py tests/test_triage.py
git commit -m "feat: batched triage classification with constrained output"
```

---

### Task 4: `menu.py` — Dispatch from queue action + wiring + README

**Files:**
- Modify: `dispatch_hub/menu.py`
- Modify: `README.md`
- Test: `tests/test_menu.py`

**Interfaces:**
- Consumes: `queue.read_queued`, `queue.move_to_in_progress`, `queue.QueuedItem`; `triage.classify`, `triage.Proposal`, `triage.DEFAULT_MODEL`; `anthropic_client.resolve_api_key`, `anthropic_client.TriageClient`, `anthropic_client.NoApiKey`.
- Produces:
  - module function `proposals_to_profile(proposals: list[Proposal], name: str = "queue-dispatch", layout: str = "grid") -> Profile` — one `Pane` per proposal, `Pane(directory, role, startup_prompt)` (role is already `None` or a real name).
  - `App.dispatch_from_queue(self)` method, wired into `run()`'s action map as `"Dispatch from queue"`.
  - `App._load_settings(self) -> dict` — reads `SETTINGS_FILE` JSON, returns `{}` if missing/corrupt.

- [ ] **Step 1: Write the failing `proposals_to_profile` test**

```python
# append to tests/test_menu.py
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_menu.py -v`
Expected: FAIL with `ImportError: cannot import name 'proposals_to_profile'`

- [ ] **Step 3: Add imports and `proposals_to_profile` to `menu.py`**

At the top of `dispatch_hub/menu.py`, add to the existing imports:

```python
from datetime import date

from . import queue as workqueue
from .anthropic_client import NoApiKey, TriageClient, resolve_api_key
from .triage import DEFAULT_MODEL, Proposal, classify
```

Add a module-level function (next to `resolve_startup_prompt`):

```python
def proposals_to_profile(proposals: list[Proposal], name: str = "queue-dispatch",
                         layout: str = "grid") -> Profile:
    panes = [Pane(p.directory, p.role, p.startup_prompt) for p in proposals]
    return Profile.new(name, layout, panes)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_menu.py -v`
Expected: PASS (existing 2 tests + the new one)

- [ ] **Step 5: Write the failing settings-guard test**

```python
# append to tests/test_menu.py
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
```

- [ ] **Step 6: Run to verify failure**

Run: `python -m pytest tests/test_menu.py::test_dispatch_returns_early_without_queue_path -v`
Expected: FAIL with `AttributeError: 'App' object has no attribute '_load_settings'` (or `dispatch_from_queue`)

- [ ] **Step 7: Implement `_load_settings` and `dispatch_from_queue`**

Add these methods to the `App` class in `dispatch_hub/menu.py`:

```python
    def _load_settings(self) -> dict:
        if SETTINGS_FILE.exists():
            try:
                return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

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
            style=STYLE, qmark=MARK,
        ).ask()
        if not chosen:
            return

        try:
            api_key = resolve_api_key(settings)
        except NoApiKey as exc:
            console.print(f"[yellow]{exc}[/yellow]")
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
```

- [ ] **Step 8: Run the guard test to verify it passes**

Run: `python -m pytest tests/test_menu.py -v`
Expected: PASS (all menu tests)

- [ ] **Step 9: Wire the action into the menu**

In `App.run()`, add the entry to the `actions` dict so it reads:

```python
        actions = {
            "Launch session": self.launch_session,
            "Create session": self.create_session,
            "Dispatch from queue": self.dispatch_from_queue,
            "Delete session": self.delete_session,
            "Manage roles": self.manage_roles,
        }
```

- [ ] **Step 10: Run the full suite**

Run: `python -m pytest tests/ -v`
Expected: PASS (all tests, including the pre-existing ones)

- [ ] **Step 11: Update the README dependency + feature notes**

In `README.md`, add `anthropic` to the dependency list/section, and add a short "Dispatch from queue" subsection documenting: set `work_queue_path` in `config/settings.json`, set `ANTHROPIC_API_KEY` (or `anthropic_api_key` in settings, noting it should not be committed), optional `triage_model` (default `claude-sonnet-4-6`). Match the README's existing heading style and density.

- [ ] **Step 12: Commit**

```bash
git add dispatch_hub/menu.py tests/test_menu.py README.md
git commit -m "feat: dispatch-from-queue menu action with triage and write-back"
```

---

## Self-Review

**1. Spec coverage** — every spec section maps to a task:
- Success criterion 1 (lists only Queued bullets) → Task 1 `read_queued` + Task 4 checkbox.
- Criterion 2 (role from roles.json, dir from discovered list, expanded prompt) → Task 3 `parse_response` clamping + Task 4 wiring of `role_names`/`directories`.
- Criterion 3 (one pane per item, charter+prompt, no loop) → Task 4 `proposals_to_profile` + unchanged `launch`.
- Criterion 4 (write-back, Done untouched) → Task 1 `move_to_in_progress` + Task 4 file write.
- Criterion 5 (unset path / no key → one-line hint) → Task 4 guard + `NoApiKey` branch.
- Criterion 6 (offline tests; unknown role→`(none)`/None; unknown dir→unresolved blocks launch) → Tasks 2/3/4 tests + the `any(p.unresolved)` block.
- Architecture forbidden-imports → Global Constraints; lazy `anthropic` import in Task 2.
- Error handling rows (missing file, empty queue, malformed JSON retry, unknown role/dir, write-back skip) → covered across Tasks 1/3/4.
- Note: `unresolved` rows block launch entirely (simpler than inline editing, which the spec offered as optional); per-row editing is deliberately deferred to keep Task 4 self-contained — call this out at review if inline edit is wanted in v1.

**2. Placeholder scan** — no TBD/TODO; every code step shows complete code; commands have expected output.

**3. Type consistency** — `Proposal` fields are identical across Tasks 3 and 4 (`item_index, item_text, role, directory, startup_prompt, reason, unresolved`). `classify` signature `(items, role_names, directories, client)` matches its call site in Task 4. `proposals_to_profile` returns `Profile` consumed by `_review_table`/`launch` (existing signatures). `resolve_api_key(settings, environ=...)` and `TriageClient(api_key, model)` match Task 2 definitions and Task 4 usage. `move_to_in_progress(text, raw_lines, today)` matches Task 1 and the Task 4 call with `date.today().isoformat()`.
