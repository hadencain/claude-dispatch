# New-Project Directory Creation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let both the manual create flow and the AI queue-dispatch flow recognize a brand-new project and `mkdir` a fresh directory for it (with confirmation) instead of forcing the work into a wrong existing folder.

**Architecture:** One new pure module `creation.py` (sanitize a name, derive parent buckets from already-discovered projects, validate, and perform the single `mkdir`) is wired into `menu.py` in two places. `triage.py` gains optional output fields so the model can flag an item as a new project and propose a slug + parent. `launcher.py` is untouched — created directories exist before launch, so `validate_directories` and the launch core work unchanged.

**Tech Stack:** Python 3.14 (`C:/Python314/python`), `questionary`, `rich`, `prompt_toolkit`, `pytest`. No new dependencies.

## Global Constraints

- Python at `C:/Python314/python` — invoke as `python`, never `python3`.
- Run tests with `python -m pytest tests/ -v`.
- `launcher.py` must not import `creation`, `menu`, `roles`, `triage`, `queue`, or `anthropic_client`.
- `creation.py` imports only stdlib (`pathlib`, `re`) — no `questionary`, `rich`, `menu`, or `discovery`.
- `triage.py` must not import `menu`, `questionary`, or `rich`.
- New directories are NEVER created silently — every creation shows the resolved absolute path and requires a confirm.
- Bare `mkdir` only — no scaffold files, no `git init`.
- Casing of a typed/proposed name is preserved (workspace dirs are `camelCase`/lowercase, not kebab-case).
- New `Proposal` fields must have defaults so existing positional construction and old JSON keep working.

## File Structure

- **Create** `dispatch_hub/creation.py` — `sanitize_dirname`, `candidate_parents`, `target_path`, `validate_new_dir`, `create_directory`.
- **Create** `tests/test_creation.py` — unit tests for the above.
- **Modify** `dispatch_hub/triage.py` — `Proposal` fields; `build_user_payload` + `classify` gain `parents`; `parse_response` reads new fields and adjusts `unresolved`; `SYSTEM_PROMPT` extended.
- **Modify** `tests/test_triage.py` — extend for new fields/payload.
- **Modify** `dispatch_hub/menu.py` — `_NEW_DIR` sentinel, `_pick_parent`, `_prompt_new_directory`, `_create_proposed_dirs`, `_parent_label`; wire both flows.
- **Modify** `tests/test_menu.py` — extend for both branches.

---

## Task 1: `creation.py` — safe directory derivation and the one mkdir

**Files:**
- Create: `dispatch_hub/creation.py`
- Test: `tests/test_creation.py`

**Interfaces:**
- Consumes: nothing (stdlib only).
- Produces:
  - `sanitize_dirname(name: str) -> str`
  - `candidate_parents(root: Path, projects: list[Path]) -> list[Path]`
  - `target_path(parent: Path, name: str) -> Path`
  - `validate_new_dir(parent: Path, name: str, root: Path) -> str | None`
  - `create_directory(path: Path) -> None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_creation.py`:

```python
from pathlib import Path
import pytest
from dispatch_hub.creation import (
    sanitize_dirname, candidate_parents, target_path,
    validate_new_dir, create_directory,
)


def test_sanitize_collapses_spaces_and_keeps_case():
    assert sanitize_dirname("Distortion plugins") == "Distortion-plugins"


def test_sanitize_strips_illegal_chars():
    assert sanitize_dirname('a/b:c?') == "a-b-c"


def test_sanitize_empty_when_nothing_usable():
    assert sanitize_dirname("   ") == ""
    assert sanitize_dirname("...") == ""


def test_candidate_parents_includes_root_and_bucket(tmp_path):
    proj = tmp_path / "src" / "pyfiles" / "thing"
    parents = candidate_parents(tmp_path, [proj])
    assert tmp_path in parents
    assert tmp_path / "src" / "pyfiles" in parents


def test_candidate_parents_excludes_outside_root(tmp_path):
    outside = tmp_path.parent / "elsewhere" / "proj"
    assert candidate_parents(tmp_path, [outside]) == [tmp_path]


def test_target_path_joins_sanitized_name(tmp_path):
    assert target_path(tmp_path, "New Thing") == tmp_path / "New-Thing"


def test_validate_rejects_empty_name(tmp_path):
    assert validate_new_dir(tmp_path, "   ", tmp_path) is not None


def test_validate_rejects_existing(tmp_path):
    (tmp_path / "dup").mkdir()
    assert validate_new_dir(tmp_path, "dup", tmp_path) is not None


def test_validate_rejects_parent_outside_root(tmp_path):
    assert validate_new_dir(tmp_path.parent, "x", tmp_path) is not None


def test_validate_ok_returns_none(tmp_path):
    assert validate_new_dir(tmp_path, "fresh", tmp_path) is None


def test_create_directory_makes_nested_dir(tmp_path):
    t = tmp_path / "a" / "b"
    create_directory(t)
    assert t.is_dir()


def test_create_directory_raises_on_existing(tmp_path):
    (tmp_path / "x").mkdir()
    with pytest.raises(FileExistsError):
        create_directory(tmp_path / "x")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_creation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dispatch_hub.creation'`.

- [ ] **Step 3: Write the implementation**

Create `dispatch_hub/creation.py`:

```python
"""Create new project directories under the workspace.

Pure derivation/validation plus one I/O function (``create_directory``). Shared
by the manual create flow and the AI queue-dispatch flow so both decide where a
new project lives the same way. Imports stdlib only — no TUI, no discovery.
"""

from __future__ import annotations

import re
from pathlib import Path

# Windows-illegal filename chars plus control chars. Each becomes a space, then
# runs of whitespace collapse to a single dash below.
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_dirname(name: str) -> str:
    """A safe single-segment directory name, casing preserved.

    Illegal characters become spaces, whitespace runs collapse to one dash, and
    leading/trailing dashes and dots are trimmed. Returns "" when nothing usable
    remains (e.g. all-whitespace or all-dots input).
    """
    cleaned = _ILLEGAL.sub(" ", name)
    cleaned = re.sub(r"\s+", "-", cleaned.strip())
    return cleaned.strip("-.")


def candidate_parents(root: Path, projects: list[Path]) -> list[Path]:
    """Parent folders a new project could live under, derived from discovered
    projects: ``root`` plus the parent of every project at or under ``root``.
    Deduped and sorted by display path. No hardcoded category list — the buckets
    track the workspace as it changes.
    """
    root = Path(root)
    out = {root}
    for p in projects:
        parent = Path(p).parent
        try:
            parent.relative_to(root)
        except ValueError:
            continue  # parent is outside the workspace; not an offerable bucket
        out.add(parent)
    return sorted(out, key=lambda p: str(p).lower())


def target_path(parent: Path, name: str) -> Path:
    """The directory that would be created for ``name`` under ``parent``."""
    return Path(parent) / sanitize_dirname(name)


def validate_new_dir(parent: Path, name: str, root: Path) -> str | None:
    """Return an error string if the new dir is invalid, else None."""
    parent, root = Path(parent), Path(root)
    if not sanitize_dirname(name):
        return "Name is empty after removing illegal characters."
    try:
        parent.relative_to(root)
    except ValueError:
        return "Parent folder must be inside the workspace."
    target = target_path(parent, name)
    if target.exists():
        return f"{target} already exists."
    return None


def create_directory(path: Path) -> None:
    """Create ``path`` (and any missing parents). Raises FileExistsError if it
    already exists — callers validate first; this is the backstop."""
    Path(path).mkdir(parents=True, exist_ok=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_creation.py -v`
Expected: PASS (12 passed).

- [ ] **Step 5: Commit**

```bash
git add dispatch_hub/creation.py tests/test_creation.py
git commit -m "feat(creation): safe new-project directory derivation and mkdir"
```

---

## Task 2: `triage.py` — new-project contract fields

**Files:**
- Modify: `dispatch_hub/triage.py`
- Test: `tests/test_triage.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `Proposal` gains `is_new_project: bool = False`, `new_dir_slug: str = ""`, `suggested_parent: str = ""`.
  - `build_user_payload(items, role_names, directories, parents: list[str] | None = None) -> str`
  - `classify(items, role_names, directories, client, parents: list[str] | None = None) -> list[Proposal]`
  - `parse_response` sets `unresolved=False` for new-project proposals.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_triage.py`:

```python
def test_payload_includes_allowed_parents():
    payload = build_user_payload(ITEMS, ROLES, DIRS, ["src/pyfiles", "."])
    data = json.loads(payload)
    assert data["allowed_parents"] == ["src/pyfiles", "."]


def _canned_new():
    return json.dumps([
        {"item_index": 0, "role": "(none)", "is_new_project": True,
         "new_dir_slug": "distortion", "suggested_parent": "src/audioProjects",
         "directory": "",
         "startup_prompt": "Scaffold and brainstorm a distortion plugin.",
         "reason": "new project"},
    ])


def test_parse_new_project_fields_and_resolved():
    props = parse_response(_canned_new(), ["make distortion"], ROLES, DIRS)
    assert props[0].is_new_project is True
    assert props[0].new_dir_slug == "distortion"
    assert props[0].suggested_parent == "src/audioProjects"
    assert props[0].unresolved is False  # empty dir is expected for a new project


def test_parse_missing_new_fields_default_to_off():
    props = parse_response(_canned("QA", "C:/ship/spotter"), ITEMS, ROLES, DIRS)
    assert props[0].is_new_project is False
    assert props[0].new_dir_slug == ""
    assert props[0].suggested_parent == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_triage.py -k "new_project or allowed_parents" -v`
Expected: FAIL — `build_user_payload()` takes 3 positional args / `Proposal` has no attribute `is_new_project`.

- [ ] **Step 3: Update the dataclass and functions**

In `dispatch_hub/triage.py`, add fields to `Proposal` (after `unresolved`):

```python
@dataclass
class Proposal:
    item_index: int
    item_text: str
    role: str | None
    directory: str
    startup_prompt: str
    reason: str
    unresolved: bool
    is_new_project: bool = False
    new_dir_slug: str = ""
    suggested_parent: str = ""
```

Replace `build_user_payload` with:

```python
def build_user_payload(items: list[str], role_names: list[str],
                       directories: list[str], parents: list[str] | None = None) -> str:
    return json.dumps({
        "items": [{"index": i, "text": t} for i, t in enumerate(items)],
        "allowed_roles": role_names,
        "allowed_directories": directories,
        "allowed_parents": parents or [],
    }, indent=2)
```

In `parse_response`, replace the per-object append block with:

```python
        idx = int(obj["item_index"])
        item_text = items[idx]
        raw_role = obj.get("role")
        role = None if raw_role == NONE_ROLE or raw_role not in role_set else raw_role
        directory = obj.get("directory", "") or ""
        prompt = (obj.get("startup_prompt") or "").strip() or item_text
        is_new = bool(obj.get("is_new_project", False))
        props.append(Proposal(
            item_index=idx,
            item_text=item_text,
            role=role,
            directory=directory,
            startup_prompt=prompt,
            reason=obj.get("reason", ""),
            unresolved=(False if is_new else directory not in dir_set),
            is_new_project=is_new,
            new_dir_slug=(obj.get("new_dir_slug") or "").strip(),
            suggested_parent=(obj.get("suggested_parent") or "").strip(),
        ))
```

Update `classify` signature and payload call:

```python
def classify(items: list[str], role_names: list[str], directories: list[str],
             client, parents: list[str] | None = None) -> list[Proposal]:
    payload = build_user_payload(items, role_names, directories, parents)
    last_error: Exception | None = None
    for _ in range(2):  # one initial attempt + one retry
        text = client.complete(SYSTEM_PROMPT, payload)
        try:
            return parse_response(text, items, role_names, directories)
        except (json.JSONDecodeError, KeyError, ValueError, TypeError, IndexError) as exc:
            last_error = exc
    raise ValueError(f"Triage returned unparseable output: {last_error}")
```

Extend `SYSTEM_PROMPT` — replace the closing sentence(s) so the model knows the new-project escape. Set it to:

```python
SYSTEM_PROMPT = (
    "You assign software work items to a role, a project directory, and a concrete "
    "startup prompt for a coding agent. You are given a list of items (each with an "
    "index), a list of allowed role names, a list of allowed project directories, and "
    "a list of allowed parent folders. For every item return one object. 'role' MUST "
    "be exactly one of the allowed role names, or the string '(none)' if none fit. "
    "If the item fits an existing project, 'directory' MUST be exactly one of the "
    "allowed directories and 'is_new_project' MUST be false. If the item describes "
    "starting a NEW project that matches none of the allowed directories, set "
    "'is_new_project' to true, leave 'directory' empty, set 'new_dir_slug' to a short "
    "folder name for it, set 'suggested_parent' to the best-fitting allowed parent, "
    "and write a 'startup_prompt' that tells the agent to scaffold and brainstorm the "
    "project from scratch (the directory will be empty). 'startup_prompt' is otherwise "
    "a clear first instruction, expanded from the terse item into something actionable. "
    "'reason' is one short phrase. Respond with ONLY a JSON array of objects with keys: "
    "item_index, role, directory, is_new_project, new_dir_slug, suggested_parent, "
    "startup_prompt, reason. No prose, no markdown fences."
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_triage.py -v`
Expected: PASS — new tests pass and all pre-existing triage tests still pass (defaults keep old JSON working).

- [ ] **Step 5: Commit**

```bash
git add dispatch_hub/triage.py tests/test_triage.py
git commit -m "feat(triage): new-project proposal fields and parent hints"
```

---

## Task 3: `menu.py` — manual flow "Create new project directory"

**Files:**
- Modify: `dispatch_hub/menu.py`
- Test: `tests/test_menu.py`

**Interfaces:**
- Consumes: `creation.candidate_parents`, `creation.validate_new_dir`, `creation.target_path`, `creation.create_directory`, `creation.sanitize_dirname`.
- Produces:
  - `App._parent_label(p: Path, root: Path) -> str` (`"."` for root, else relative posix)
  - `App._pick_parent(root: Path)` → parent POSIX path string or `BACK`
  - `App._prompt_new_directory()` → created dir POSIX path string or `BACK`
  - `_pick_directory` returns the created path when the new-dir choice is taken.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_menu.py`:

```python
def _scripted(values):
    """A fake asker returning successive values from ``values`` per call."""
    it = iter(values)
    return lambda *a, **k: next(it)


def test_pick_directory_create_branch_creates_and_returns(tmp_path, monkeypatch):
    import dispatch_hub.menu as menu
    app = _app()
    monkeypatch.setattr(app, "_workspace_root", lambda: tmp_path)
    app._projects = []  # skip discovery
    # First ask_select_back picks the create-new sentinel; second (parent picker)
    # returns the workspace root.
    monkeypatch.setattr(menu, "ask_select_back",
                        _scripted([menu._NEW_DIR, tmp_path.as_posix()]))
    monkeypatch.setattr(menu, "ask_text", lambda *a, **k: "New Thing")
    monkeypatch.setattr(menu, "ask_confirm", lambda *a, **k: True)
    result = app._pick_directory(None)
    assert result == (tmp_path / "New-Thing").as_posix()
    assert (tmp_path / "New-Thing").is_dir()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_menu.py::test_pick_directory_create_branch_creates_and_returns -v`
Expected: FAIL — `module 'dispatch_hub.menu' has no attribute '_NEW_DIR'`.

- [ ] **Step 3: Implement the manual-flow branch**

In `dispatch_hub/menu.py`:

Add the import (with the other `from .` imports):

```python
from .creation import (
    candidate_parents, create_directory, sanitize_dirname, target_path,
    validate_new_dir,
)
```

Add the sentinel next to `_MANUAL_DIR`:

```python
_NEW_DIR = "\x00newdir"
```

Add three methods to `App` (place them just above `_pick_directory`):

```python
    @staticmethod
    def _parent_label(p: Path, root: Path) -> str:
        """Display/transport label for a parent: '.' for the root itself,
        else its path relative to the root in posix form."""
        if p == root:
            return "."
        try:
            return p.relative_to(root).as_posix()
        except ValueError:
            return p.as_posix()

    def _pick_parent(self, root: Path):
        """Select a parent folder from the workspace's existing buckets.

        Returns a parent POSIX path string, or BACK if cancelled.
        """
        choices = []
        for p in candidate_parents(root, self._projects):
            label = "· (workspace root)" if p == root else p.relative_to(root).as_posix()
            choices.append(questionary.Choice(title=label, value=p.as_posix()))
        return ask_select_back(
            "Create under which folder?", choices=choices, use_search_filter=True,
        )

    def _prompt_new_directory(self):
        """Prompt for a name + parent, create the directory, return its path.

        Returns the created directory's POSIX path, or BACK if cancelled. Never
        creates without a confirm; re-prompts on any validation failure.
        """
        root = self._workspace_root()
        if self._projects is None:
            self._projects = discover_projects(root)
        while True:
            name = ask_text("New project name (blank to go back):")
            if name is None or not name.strip():
                return BACK
            parent_ans = self._pick_parent(root)
            if parent_ans is BACK:
                continue
            parent = Path(parent_ans)
            err = validate_new_dir(parent, name, root)
            if err:
                console.print(f"[red]{err}[/red]")
                continue
            target = target_path(parent, name)
            if not ask_confirm(f"Create new project at {target}?"):
                continue
            try:
                create_directory(target)
            except OSError as exc:
                console.print(f"[red]Could not create {target}: {exc}[/red]")
                continue
            self._projects.append(target)
            console.print(f"[green]Created {target}.[/green]")
            return target.as_posix()
```

In `_pick_directory`, add the new choice and handle the sentinel. Insert the choice line just before the manual-entry choice:

```python
        choices.append(questionary.Choice(title="✚ Create new project directory", value=_NEW_DIR))
        choices.append(questionary.Choice(title="✎ Type a path manually", value=_MANUAL_DIR))
```

And handle the sentinel right after the `BACK` check:

```python
        if ans is BACK:
            return BACK
        if ans == _NEW_DIR:
            return self._prompt_new_directory()
        if ans == _MANUAL_DIR:
            ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_menu.py -v`
Expected: PASS — new test passes, existing menu tests unaffected.

- [ ] **Step 5: Commit**

```bash
git add dispatch_hub/menu.py tests/test_menu.py
git commit -m "feat(menu): create new project directory in the manual flow"
```

---

## Task 4: `menu.py` — AI queue flow creates proposed directories

**Files:**
- Modify: `dispatch_hub/menu.py`
- Test: `tests/test_menu.py`

**Interfaces:**
- Consumes: `creation.*` (already imported in Task 3), `App._pick_parent`, `App._parent_label`; `Proposal.is_new_project / new_dir_slug / suggested_parent` (Task 2).
- Produces:
  - `App._create_proposed_dirs(proposals: list[Proposal], root: Path) -> None` — mutates accepted proposals' `directory`; marks skipped new-project proposals `unresolved = True`.
  - `dispatch_from_queue` passes parents to `classify` and runs `_create_proposed_dirs` before the review table.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_menu.py`:

```python
def _new_prop(slug="distortion", parent="."):
    return Proposal(0, "make distortion", None, "", "scaffold it", "new",
                    unresolved=False, is_new_project=True,
                    new_dir_slug=slug, suggested_parent=parent)


def test_create_proposed_dirs_creates_and_sets_directory(tmp_path, monkeypatch):
    import dispatch_hub.menu as menu
    app = _app()
    app._projects = []
    prop = _new_prop()
    monkeypatch.setattr(menu, "ask_select", lambda *a, **k: "create")
    app._create_proposed_dirs([prop], tmp_path)
    assert prop.directory == (tmp_path / "distortion").as_posix()
    assert (tmp_path / "distortion").is_dir()
    assert prop.unresolved is False


def test_create_proposed_dirs_skip_marks_unresolved(tmp_path, monkeypatch):
    import dispatch_hub.menu as menu
    app = _app()
    app._projects = []
    prop = _new_prop()
    monkeypatch.setattr(menu, "ask_select", lambda *a, **k: "skip")
    app._create_proposed_dirs([prop], tmp_path)
    assert prop.directory == ""
    assert prop.unresolved is True
    assert not (tmp_path / "distortion").exists()


def test_create_proposed_dirs_ignores_existing_project_items(tmp_path, monkeypatch):
    import dispatch_hub.menu as menu
    app = _app()
    app._projects = []
    prop = Proposal(0, "fix spotter", "QA", "C:/ship/spotter", "go", "r",
                    unresolved=False)
    # ask_select must never be called for a non-new item
    monkeypatch.setattr(menu, "ask_select",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    app._create_proposed_dirs([prop], tmp_path)
    assert prop.directory == "C:/ship/spotter"
```

The `Proposal` import already exists at the top of `tests/test_menu.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_menu.py -k create_proposed_dirs -v`
Expected: FAIL — `App` has no attribute `_create_proposed_dirs`.

- [ ] **Step 3: Implement `_create_proposed_dirs` and wire the flow**

Add the method to `App` (place it just above `dispatch_from_queue`):

```python
    def _create_proposed_dirs(self, proposals: list[Proposal], root: Path) -> None:
        """For each new-project proposal, interactively confirm and create its
        directory, setting ``proposal.directory`` to the created path. A skipped
        proposal is marked unresolved so the existing launch guard blocks it.
        Non-new proposals are left untouched.
        """
        for prop in proposals:
            if not prop.is_new_project:
                continue
            name = prop.new_dir_slug or sanitize_dirname(prop.item_text)
            parent = root if prop.suggested_parent in ("", ".") else root / prop.suggested_parent
            while True:
                target = target_path(parent, name)
                console.print(f"[cyan]New project for:[/cyan] {prop.item_text}")
                action = ask_select(
                    f"Proposed directory: {target}",
                    choices=[
                        questionary.Choice("Create it", "create"),
                        questionary.Choice("Rename folder", "rename"),
                        questionary.Choice("Change parent folder", "parent"),
                        questionary.Choice("Skip (leave unresolved)", "skip"),
                    ],
                )
                if action in (None, "skip"):
                    prop.unresolved = True
                    break
                if action == "rename":
                    typed = ask_text("Folder name:", default=name)
                    if typed and typed.strip():
                        name = typed.strip()
                    continue
                if action == "parent":
                    picked = self._pick_parent(root)
                    if picked is not BACK:
                        parent = Path(picked)
                    continue
                err = validate_new_dir(parent, name, root)
                if err:
                    console.print(f"[red]{err}[/red]")
                    continue
                try:
                    create_directory(target)
                except OSError as exc:
                    console.print(f"[red]Could not create {target}: {exc}[/red]")
                    continue
                prop.directory = target.as_posix()
                self._projects.append(target)
                console.print(f"[green]Created {target}.[/green]")
                break
```

In `dispatch_from_queue`, replace the directory/classify block (currently building `directories` and calling `classify`) with one that also passes parents and creates proposed dirs:

```python
        root = self._workspace_root()
        if self._projects is None:
            self._projects = discover_projects(root)
        directories = [p.as_posix() for p in self._projects]
        parents = [self._parent_label(p, root) for p in candidate_parents(root, self._projects)]

        try:
            proposals = classify([it.text for it in chosen], role_names, directories, client, parents)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            return

        self._create_proposed_dirs(proposals, root)

        profile = proposals_to_profile(proposals)
```

(The existing review table, unresolved check, confirm, `validate_directories`, and `launch` lines that follow are unchanged — created dirs now exist, skipped ones are flagged `unresolved`.)

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest tests/ -v`
Expected: PASS — all new tests pass; the existing `dispatch_from_queue` tests still pass (their stubbed `classify` returns `[]`, so `_create_proposed_dirs([], root)` is a no-op).

- [ ] **Step 5: Commit**

```bash
git add dispatch_hub/menu.py tests/test_menu.py
git commit -m "feat(menu): create proposed directories during queue dispatch"
```

---

## Verification

End-to-end, after all tasks:

1. `python -m pytest tests/ -v` — full suite green.
2. Manual flow: `python -m dispatch_hub` → **Create session** → name/layout → at the directory step choose **✚ Create new project directory** → type a name (e.g. `Distortion Master`) → pick a parent bucket → confirm → verify the folder is created on disk under the chosen parent and the pane proceeds to role/prompt with that directory.
3. AI flow: with `work_queue_path` and an Anthropic key set, **Dispatch from queue**, select a clearly-new item (e.g. "brainstorming Distortion plugins") → at the proposal step confirm **Create it** → verify the directory is created, the review table shows it, and launching opens a pane in the empty dir running the brainstorm-first startup prompt.
4. Skip path: in the AI flow choose **Skip** for a new-project proposal → verify launch is blocked with the existing unresolved-directory message and no directory was created.

## Notes / deliberate deviations from the spec

- The spec's Components prose mentions tagging created dirs with `(new)` in the review table. The plan omits that tag to avoid threading new-ness through `Profile`/`_review_table`; per-directory green "Created …" confirmations already make every creation visible at the moment it happens. Behavior-equivalent for the user; no success criterion depends on the tag.
