# New-Project Directory Creation — Design

## What this is

A directory-creation capability added to Claude Dispatch Hub so that starting a
brand-new project no longer forces the work into a wrong existing folder. Today
both the manual create flow and the AI queue-dispatch flow can only *select* an
existing project directory: the manual picker offers discovered projects plus a
type-a-path escape hatch, and the triage model is constrained to pick a
`directory` from `allowed_directories`. A new-project item (e.g. the queued
"brainstorming Distortion plugins") matches nothing, so the model either jams it
into an unrelated folder or returns an off-list path that is flagged
`unresolved` and blocks launch. This feature teaches both flows to recognize
new-project intent and `mkdir` a fresh directory — bare (no scaffold, no git;
the launched Claude session does its own scaffolding) — under a parent the user
chooses from the workspace's existing category buckets. Creation is always
explicit: the resolved path is shown and confirmed before any directory is made.

## Success criteria

1. In the manual create flow, `_pick_directory` offers a **✚ Create new project
   directory** choice. Selecting it prompts for a name, then a parent (defaulting
   to the workspace root, with the workspace's existing buckets — `src/pyfiles`,
   `src/audioProjects`, `src/3dPrintingTools`, etc. — offered as choices),
   confirms the full target path, creates the directory, and returns its path so
   the pane continues into role/prompt selection exactly like a picked project.
2. The newly created directory is appended to the session's cached project list,
   so a second pane in the same create session sees it in the normal picker
   without a rescan.
3. In the AI queue flow, an item describing a brand-new project is returned by
   triage with `is_new_project: true`, a `new_dir_slug`, a `suggested_parent`
   drawn from the allowed parents, and a `startup_prompt` that instructs the
   agent to scaffold and brainstorm the project from scratch. Such a proposal is
   **not** flagged `unresolved`.
4. Before the review table, `dispatch_from_queue` walks each new-project
   proposal through an interactive confirm-and-create step: it shows
   `parent/slug` and lets the user accept, rename, repick the parent, or skip.
   On accept the directory is created and the proposal's `directory` is set to
   the new path; on skip the proposal stays directory-less and is treated as
   unresolved (blocking launch with the existing message).
5. No directory is ever created silently. Every creation — manual or AI — shows
   the resolved absolute path and requires a confirm. Attempting to create a
   directory that already exists, or one whose name sanitizes to empty, or one
   outside the workspace root, is rejected with a one-line error and re-prompts;
   no traceback.
6. After a confirmed new-project dispatch, `validate_directories` passes (the
   dirs now exist) and launch proceeds unchanged: each new pane runs `claude`
   in its freshly created directory with the model-written brainstorm-first
   startup prompt.
7. The full test suite runs offline: pure creation helpers (sanitize, parent
   derivation, validation) are tested without I/O; `mkdir` is tested against a
   temp dir including the raises-on-existing case; triage parsing of the new
   fields is tested with canned JSON; the menu branches are tested with
   monkeypatched askers and a temp workspace.

## Stack

- Python 3.14 (`C:/Python314/python`), existing TUI deps: `questionary`,
  `rich`, `prompt_toolkit`. No new dependencies.

## Architecture — one new module, launcher stays blind

One new module joins the package: **`creation.py`** — pure helpers plus a single
I/O function. It holds all knowledge about turning a name + parent into a safe,
validated directory, so the manual flow and the AI flow share one source of
truth and `menu.py` remains the only orchestrator.

The existing direction-of-knowledge rules are preserved and extended:

- `launcher.py` → must not import `creation` (or `menu`, `roles`, `triage`,
  `queue`, `anthropic_client`). It still receives a finished `Profile` whose
  pane directories already exist on disk.
- `creation.py` → imports nothing from the package but `pathlib`/stdlib. It does
  not import `questionary`, `rich`, `menu`, or `discovery`. It is handed a root,
  a project list, a name, and a parent; it returns paths, validation strings, or
  performs the one `mkdir`. It never prompts and never renders.
- `triage.py` → gains output fields but still must not import `menu`,
  `questionary`, or `rich`. It returns structured proposals; it does not create
  directories.
- `menu.py` → the only place creation is wired into the two flows, mirroring how
  it already wires `discovery` + `launcher`.

## Components

**`creation.py` — safe directory derivation and the one mkdir.**

- `sanitize_dirname(name) -> str` — strips filesystem-illegal characters
  (`<>:"/\|?*` and control chars), trims surrounding whitespace, and collapses
  internal whitespace runs to a single `-`. Casing is **preserved** — the
  workspace's directories are `camelCase`/lowercase (`pyfiles`, `audioProjects`,
  `financeTools`), not kebab-case, so no style is forced. Returns `""` when
  nothing usable remains.
- `candidate_parents(root, projects) -> list[Path]` — derives parent buckets
  *from the already-discovered projects*: `{root} ∪ {p.parent for p in projects}`,
  restricted to paths at or under `root`, deduped, sorted by display path. There
  is no hardcoded category list — the buckets stay correct as the workspace
  mutates. This deliberately reuses `discovery.py`'s output rather than
  re-walking the tree.
- `validate_new_dir(parent, name, root) -> str | None` — returns an error string
  or `None`. Rejects: a name that sanitizes to empty, a target that already
  exists, and a parent that is not at or under `root`.
- `create_directory(path) -> None` — the only I/O. `path.mkdir(parents=True,
  exist_ok=False)`. Raises `FileExistsError` on a pre-existing target (callers
  validate first; the raise is a backstop).

**`menu.py` — manual flow (`_pick_directory`).** A `✚ Create new project
directory` choice is added above "Type a path manually", behind a `_NEW_DIR`
sentinel. Selecting it runs a small sub-loop: prompt name → pick parent from
`candidate_parents` (displayed relative to root; root shown as the workspace
root, set as default) → validate → confirm the resolved absolute path →
`create_directory`. On success the new path is appended to `self._projects` and
returned as a POSIX path string, flowing into `pane_role` exactly like a picked
project. Any cancel/Esc returns `BACK`; any validation failure prints a one-line
error and re-prompts.

**`triage.py` — new-project contract extension.** `build_user_payload` gains an
`allowed_parents` list (relative parent display paths). `SYSTEM_PROMPT` is
extended: *if an item describes starting a NEW project that matches none of the
allowed directories, set `is_new_project: true`, set `new_dir_slug` to a short
folder name, set `suggested_parent` to the best-fitting allowed parent, and
write a `startup_prompt` that tells the agent to scaffold and brainstorm the
project from scratch (the dir will be empty).* `Proposal` gains
`is_new_project: bool`, `new_dir_slug: str`, `suggested_parent: str` (all
defaulted so old JSON still parses). `parse_response` reads them and sets
`unresolved = False` for new-project proposals — an empty `directory` on a
new-project item is expected, not a failure — while non-new items keep the
existing `directory not in dir_set` rule.

**`menu.py` — AI flow (`dispatch_from_queue`).** `build_user_payload` is now
called with the derived parents. After `classify`, and before the review table,
a new `_create_proposed_dirs(proposals)` pass handles each `is_new_project`
proposal interactively: it shows `parent/slug`, then offers accept / rename /
change parent / skip. Accept validates and `create_directory`s, sets
`proposal.directory` to the new POSIX path, and appends to `self._projects`.
Skip leaves `directory` empty so the existing unresolved-blocks-launch path
reports it. The review table tags created directories with `(new)`. Because the
directories exist by the time `validate_directories` runs, the launch core is
untouched.

## Data flow

Manual: `create_session` → `_pick_directory` → (new branch) name + parent via
`creation.candidate_parents`/`sanitize_dirname`/`validate_new_dir` →
`create_directory` → path string → `Pane`.

AI: `dispatch_from_queue` → `discover_projects` → `candidate_parents` →
`triage.classify` (now emits new-project proposals) → `_create_proposed_dirs`
(confirm + `create_directory`) → review table → existing
`validate_directories` → `launch`.

## Error handling

- Name sanitizes to empty / target exists / parent outside root → one-line
  `console.print` error, re-prompt (manual) or re-offer accept/rename/skip (AI).
  Never a traceback.
- Cancel/Esc at any creation sub-step returns `BACK` (manual) or is treated as
  skip (AI), never a partial directory.
- `create_directory` failing for an OS reason (permissions, etc.) surfaces as a
  one-line error and aborts that creation; the flow returns to a safe state.

## Testing

- `tests/test_creation.py` — `sanitize_dirname` (spaces, illegal chars, empty
  result, casing preserved); `candidate_parents` (derivation, dedupe, root
  inclusion, out-of-root exclusion); `validate_new_dir` (empty, existing,
  outside-root, ok); `create_directory` (creates under `tmp_path`, raises on
  existing).
- `tests/test_triage.py` (extend) — `build_user_payload` includes
  `allowed_parents`; `parse_response` maps the three new fields and sets
  `unresolved=False` for a new-project object while keeping the existing rule for
  normal items; missing fields default cleanly.
- `tests/test_menu.py` (extend) — `_pick_directory` create branch with
  monkeypatched askers and a `tmp_path` workspace returns the new path and the
  directory exists; `dispatch_from_queue` with a canned new-project proposal and
  an auto-accept asker creates the dir and sets `directory`; a skipped proposal
  stays unresolved.

## Out of scope (YAGNI)

- No scaffolding (CLAUDE.md, README, /scratch) and no `git init` — bare `mkdir`
  by decision; the launched session scaffolds as needed.
- No persistent "recent parents" memory; parents are re-derived each run.
- No rename/move/delete of project directories from the hub.
