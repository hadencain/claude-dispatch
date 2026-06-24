# Work Queue Dispatch — Design

## What this is

A triage-and-dispatch flow added to Claude Dispatch Hub that turns terse bullets in an Obsidian work-queue markdown file into a live multi-pane Claude Code session. It reads the queue's `## Queued` section, lets you select which items to tend, asks the Anthropic API to assign each selected item a role (charter), a target project directory, and an expanded startup prompt, shows the proposals in the existing review table for confirmation, then launches one tiled Windows Terminal window with a pane per item — reusing the hub's existing launch core verbatim. It inherits its parse-confirm-launch shape from the hub's manual create/launch flow, its directory candidate set from `discovery.py`, and its charter set from `roles.json`. It runs as one new menu action inside the existing `python -m dispatch_hub` TUI. There is no polling, no daemon, and no recurring loop: dispatch happens once, on demand, for the items you pick.

## Success criteria

1. With `work_queue_path` set in `config/settings.json` and an Anthropic key available, choosing **Dispatch from queue** lists exactly the bullet lines under `## Queued` — nothing from `## In Progress` or `## Done`, and verbatim bullet text (project prefixes like `claude-dispatch  …` shown intact).
2. After selecting one or more items and confirming triage, a review table maps each selected item to a role whose name exists in `roles.json` and a directory that exists in the discovered project list, plus an expanded startup prompt longer and more actionable than the raw bullet.
3. Confirming the launch opens a single Windows Terminal window with one pane per dispatched item; each pane runs `claude --append-system-prompt <assigned charter> <expanded prompt>` in the assigned directory. No pane runs `/loop` or any recurring construct.
4. Immediately after a confirmed launch, every dispatched bullet is gone from `## Queued` and present under `## In Progress` in the queue file; the `## Done` section and all non-dispatched bullets are byte-for-byte unchanged.
5. With `work_queue_path` unset or empty, choosing **Dispatch from queue** prints a one-line setup hint naming the setting and returns to the menu without traceback. The same single-line-hint behavior holds when no Anthropic key is resolvable.
6. The full test suite runs offline with no network and no real terminal: triage with a mocked client maps canned JSON to `Pane` objects; an item assigned an unknown role clamps to `(none)`, and an item assigned an unresolvable directory is flagged `unresolved` and blocks launch until fixed or dropped.

## Stack

- Python 3.14 (`C:/Python314/python`), existing TUI deps: `questionary`, `rich`, `prompt_toolkit`.
- New runtime dependency: `anthropic` (the official SDK). Added to `requirements.txt` and the README dependency section.
- No dependency on Ship's `src/shared/claude` — the tool must stay self-contained and shareable. A thin in-package client wraps `anthropic` directly.

## Architecture — new modules, one direction of knowledge, launcher stays blind

Three new modules join the package. The existing rule that `launcher.py` is pure command-construction extends to them: **`launcher.py` imports none of `queue`, `triage`, or `anthropic_client`** — same prohibition that already forbids it importing `menu`/`roles`. Knowledge flows one way: `menu` orchestrates; `triage` depends on `anthropic_client` and on the plain data it is handed; `queue` depends on nothing but the standard library.

Forbidden relationships, stated explicitly:

- `launcher.py` → must not import `queue`, `triage`, `anthropic_client`, `menu`, or `roles`. It receives a finished `Profile` and charters dict, exactly as today.
- `queue.py` → must not import `anthropic`, `triage`, `menu`, or any TUI. It is pure markdown parse/serialize over a string; it never makes network calls and never decides anything.
- `triage.py` → may import `anthropic_client` and the `models`/`roles` data it classifies against. It must not import `menu`, `questionary`, or `rich`; it returns structured proposals, it does not render or prompt.
- `anthropic_client.py` → the only module that imports `anthropic`. Nothing else in the package may import the SDK directly.

`menu.py` is the only place these are wired together, mirroring how it already wires `roles` + `launcher`.

## Components

**`queue.py` — parse and rewrite the work-queue markdown.** Splits the file into its `##`-delimited sections, exposes the `## Queued` bullets as a list of `(raw_line, text)` pairs, and provides a `move_to_in_progress(lines)` that relocates the exact matched bullet lines from `## Queued` to the top of `## In Progress`, appending ` (dispatched YYYY-MM-DD)` to each moved line. Rewrite is surgical: every byte outside the moved lines — blank lines, the `## Done` section, indentation, ordering — is preserved, because the file is a human-edited Obsidian note that other tools and a session-start hook also write. Note: the hub's existing stores (`ProfileStore`, `RoleStore`) own JSON they fully control and rewrite wholesale; `queue.py` deviates by treating the file as foreign and append/move-only, never reserializing the whole document, because corrupting a shared note is worse than any feature it enables.

**`anthropic_client.py` — thin triage client.** Wraps a single `messages.create` call: takes a system prompt and a user payload, returns the text. Key resolution order: `ANTHROPIC_API_KEY` env var first, then `anthropic_api_key` in `settings.json` (supported but discouraged — flagged in docs as unsafe to commit). Model defaults to `claude-sonnet-4-6` (a classification call does not need Opus) and is overridable via `triage_model` in `settings.json`. Raises a typed `NoApiKey` when neither key source resolves, so `menu` can show the setup hint instead of a traceback. Note: this is the deliberate deviation from reusing `src/shared/claude` — that module loads keys from the Ship-specific `AppConfig("ship")` and ties the launcher to one machine's workspace; vendoring a ~30-line client keeps the tool a clean standalone package.

**`triage.py` — one batched classification call.** Takes the selected items, the role names from `roles.json`, and the discovered project list, and issues a **single** Anthropic call returning a JSON array of `{item_index, role, directory, startup_prompt, reason}`. Batched rather than per-item so the model sees all selections at once and can avoid assigning two conflicting items to the same directory, and so cost is one call regardless of selection size. Output is constrained, not trusted: `role` is clamped to an existing role name or `(none)`; `directory` must match a discovered/existing path or the item is marked `unresolved`; `startup_prompt` falls back to the raw bullet if empty. On malformed JSON it retries once, then aborts the whole dispatch (no partial launch). Returns a list of proposal objects carrying the `unresolved` flag; it renders nothing.

**`menu.py` — the Dispatch from queue action.** New top-level action alongside Launch/Create/Delete/Manage roles. Reads `work_queue_path` from settings; if unset/empty, prints the one-line hint and returns. Lists `## Queued` bullets via `questionary` multi-select. Calls `triage.classify(...)`; on `NoApiKey` prints the hint and returns. Builds an **ephemeral** `Profile` (grid layout, one pane per item) from the proposals and renders it through the existing `_review_table`, with `unresolved` rows marked. The user may edit a row's directory/role/prompt, drop a row, or — offered as an option — save the ephemeral profile to `profiles/` for reuse. Launch is blocked while any row is `unresolved`. On confirm: call the existing `launch(...)` unchanged, then `queue.move_to_in_progress(...)` for the dispatched lines. Note: create-session persists a named profile; dispatch builds a throwaway one by default, because queue items are transient and naming each dispatch would be friction — saving is opt-in, not the default.

## Command / API surface

| Surface | Behavior |
|---|---|
| Menu: `Dispatch from queue` | Read queue → multi-select items → triage → review → confirm → launch + write-back |
| `settings.json: work_queue_path` | Absolute path to the Obsidian work-queue `.md`. Empty/unset disables the feature |
| `settings.json: triage_model` | Anthropic model id for triage. Default `claude-sonnet-4-6` |
| `settings.json: anthropic_api_key` | Optional key fallback; env `ANTHROPIC_API_KEY` takes precedence; discouraged in committed files |
| `queue.read_queued(text)` | → list of `(raw_line, text)` for `## Queued` bullets |
| `queue.move_to_in_progress(text, lines)` | → new file text with lines moved to `## In Progress`, dated |
| `triage.classify(items, roles, dirs)` | → list of proposals `{item_index, role, directory, startup_prompt, reason, unresolved}` |

## Defaults policy

Out of the box, with no `settings.json`, the feature is inert and invisible in effect: the menu entry exists but, lacking `work_queue_path`, only prints how to enable it. This is what makes the tool shareable — a fresh clone never reaches for a path that exists only on the author's machine. When configured, the defaults are: grid layout (the hub's even-tiling engine), `claude-sonnet-4-6` for triage, env-var key resolution, ephemeral profiles, and write-back to `## In Progress` on launch. The offline assertion proving defaults are functional: a test feeds a fixture queue plus canned triage JSON through `classify` with a mocked client and asserts the resulting `Profile` has one pane per selected item, each pane's role is a real role name or `(none)`, and each directory is one of the supplied candidates.

## Error handling

- `work_queue_path` unset/empty → one-line hint naming the setting, return to menu. No traceback.
- No resolvable Anthropic key (`NoApiKey`) → one-line hint (`set ANTHROPIC_API_KEY`), return to menu.
- Queue file missing or unreadable → log the path and the error, return to menu; never create the file.
- `## Queued` empty or absent → "Queue has no items to dispatch.", return to menu.
- Triage returns malformed JSON → retry once; on second failure, show the raw response and abort dispatch entirely (no panes spawned).
- Triage assigns an unknown role → clamp to `(none)`, surface in the review table.
- Triage assigns an unresolvable directory → mark the row `unresolved`; launch is blocked until the user sets a valid directory or drops the row.
- A resolved directory that does not exist on disk → caught by the existing `validate_directories` pre-launch check, same as manual launch.
- Write-back can't match a dispatched line in `## Queued` (file edited mid-session) → skip that line's move, warn which item, leave the file otherwise untouched; the session still launched.

## Testing

- **Queue parse** (`test_queue.py`, offline): fixture markdown with all three sections → assert `read_queued` returns only `## Queued` bullets with verbatim text. Assert `move_to_in_progress` for one bullet produces output where that line is dated under `## In Progress`, the bullet is gone from `## Queued`, and the `## Done` section plus untouched bullets are byte-identical (string equality on those slices).
- **Triage mapping** (`test_triage.py`, offline, mocked client): inject a fake `anthropic_client` returning canned JSON. Assert proposals map to `Pane` fields; an unknown role clamps to `(none)`; an unknown directory sets `unresolved=True`; an empty `startup_prompt` falls back to the raw bullet. Assert malformed JSON triggers exactly one retry then raises without launching.
- **Client key resolution** (`test_anthropic_client.py`, offline): env var present → used; env absent, settings key present → used; neither → raises `NoApiKey`. The SDK call itself is mocked; no network.
- **Menu wiring** (`test_menu` additions): with no `work_queue_path`, the action returns without calling triage; with an `unresolved` row, launch is not invoked.
- **Launch** reuses the existing `build_command`/`render_pane_script` tests unchanged — dispatch produces a `Profile`, and the launch path below it is already covered. No real `wt.exe` or `claude` is ever invoked in tests.
