# Claude Dispatch Hub — Design

## What this is

A Windows CLI launcher that turns a saved profile into a live multi-agent Claude Code session in one Windows Terminal window. The session-profile concept is inherited from `tmuxinator` (named, reusable, multi-pane terminal layouts described in a file) and from VS Code multi-root workspaces (one window, many project roots); the launch mechanism is Windows Terminal's `wt.exe` pane-splitting command grammar. It runs as a single interactive Python process — `python -m dispatch_hub` — that reads/writes JSON, builds a `wt.exe` command, and hands off. It does not stay resident after launch and never wraps or proxies the `claude` processes it spawns.

Each pane is a Claude Code instance pinned to a project directory, optionally carrying a persistent **role** (system-prompt charter) and a **startup prompt** (first message). The tool's job is to make "four agents, four directories, four roles, this layout" a one-keystroke action instead of four manual `cd && claude` invocations.

## Success criteria

Each is verifiable from outside the code.

1. From a fresh checkout with no config, first run seeds `config/roles.json` with four built-in roles (Architect, Backend, Frontend, QA) and presents a main menu with no saved profiles.
2. Creating a profile with two panes (two real directories, layout `horizontal`), then choosing **Launch**, opens **one** Windows Terminal window split into two side-by-side panes; the left pane's working directory is the first directory and the right pane's is the second, each running `claude`.
3. A pane assigned the Backend role launches `claude` such that asking it "what is your role?" reflects the Backend charter — i.e. `--append-system-prompt` carried the charter text intact, including quotes and slashes.
4. A pane with startup prompt preset **Plan new project** sends `/plan` as its first input; a pane with **Continue development** sends the continue-development sentence; a pane with no role launches plain `claude` with only its startup prompt.
5. Launching a profile whose one directory no longer exists **does not open a terminal** — it prints which directory is missing and returns to the menu.
6. After a launch, `config/.launch/` contains no leftover `.ps1` files (each self-deleted), and re-launching the same profile succeeds without manual cleanup.
7. Layout `vertical` stacks panes top-to-bottom; `horizontal` places them left-to-right; `grid` produces a roughly square arrangement for 3+ panes. The first two are exact; grid is best-effort.
8. The command builder is exercised by unit tests that assert the exact `wt.exe` argument list for each layout, with and without roles, including a charter containing `"` and `/`, with **no terminal launched**.

## Stack

- Python 3.14 (`C:/Python314/python`; invoke as `python`)
- `rich` — profile/role review tables and menu rendering
- `questionary` — arrow-key selection and prompts
- Windows 11 + Windows Terminal (`wt.exe`) + PowerShell (`pwsh`)
- `claude` (Claude Code CLI) must be on `PATH`
- Standard library only beyond the two display deps; JSON via `json`, process launch via `subprocess` (arg list, no shell).

## Architecture — one process, one direction of knowledge, launch-core isolated

Three concentric layers. Knowledge flows inward-out only:

- **Core (`models.py`, `launcher.py`, `validation.py`)** — pure data and pure command construction. `launcher.py` takes a `Profile` and returns/executes a `wt.exe` command. **Forbidden:** core never imports from `menu.py` or `roles.py`'s defaults seeding; `launcher.py` never calls `questionary`/`rich`, never reads JSON from disk, never prompts. It is given a fully-resolved `Profile` and nothing else.
- **Persistence (`store.py`, `roles.py`)** — JSON load/save for profiles and roles. May import `models`. **Forbidden:** never imports `menu.py`; never launches anything.
- **Interface (`menu.py`, `main.py`)** — the only layer allowed to call `questionary`, `rich`, and to orchestrate. Imports everything below it.

The non-negotiable constraint: **`launcher.py` is testable and runnable with zero I/O dependencies beyond writing its scripts and calling `subprocess`.** Given a `Profile` literal, it emits a deterministic `wt.exe` arg list. This is what makes the launch core (the only genuinely risky part) provable in isolation before any menu exists.

## Components

**`models.py`** — `Role`, `Pane`, `Profile` dataclasses with `to_dict`/`from_dict`. `Pane` holds `directory`, `role: str | None`, `startup_prompt: str`, `title: str | None`. `Profile` holds `name`, `layout`, `panes`, `created`, `modified`. Startup-prompt presets are resolved to literal strings at save time, so a stored profile is fully self-contained and replayable even if preset wording later changes.

**`roles.py`** — Ships four built-in charters (Architect, Backend, Frontend, QA) seeded into `config/roles.json` on first run; all are editable and new roles can be added. `builtin: bool` marks the seeded four but does not lock them. Note: tmuxinator has no notion of per-pane agent identity — panes are just shells running commands. This adds a persona layer because the entire point is differentiated agents, not differentiated terminals.

**`store.py`** — One JSON file per profile under `config/profiles/<name>.json`. Per-file (not a single `profiles.json` blob) so profiles are independently hand-editable, diffable, and deletable. Corrupt JSON in one profile is skipped with a warning during listing, never crashes the menu.

**`validation.py`** — Directory existence checked at two points: on **save** (warn, allow, flag the pane) and immediately pre-**launch** (hard block, list offenders, refuse to open a terminal). Pre-launch also resolves `wt.exe` and `claude` via `shutil.which` and fails with a fix hint if `claude` is absent — otherwise panes would open and instantly error, which is worse than not opening. Profile names validated as non-empty and filesystem-safe.

**`launcher.py`** — The launch core, three steps:
1. **Per-pane script generation.** For each pane, write a `.ps1` to `config/.launch/`. The script self-deletes as its first executed line (`Remove-Item -LiteralPath $PSCommandPath -Force`, safe because `pwsh -File` reads and parses the whole script before executing, then releases the handle), then `Set-Location` to the directory and invokes `claude`. Charter and startup prompt are embedded as PowerShell here-strings (`@'…'@`), which eliminates all `wt`→`pwsh`→`claude` escaping — long charters with quotes and slashes pass through verbatim. If `role is None`, the `--append-system-prompt` segment is omitted.
2. **Command assembly.** First pane is `wt.exe new-tab`; subsequent panes are `split-pane <flag>`, chained with the literal `` `; `` separator. Each segment carries `-d <dir>`, `--title <title>`, and `pwsh -NoExit -File <script>`.
3. **Exec.** `subprocess.run([...])` with an argument list and no shell, so Python owns process-level quoting and cmd.exe escaping is never in play.
   - Stale-script sweep runs at the **start** of every launch as a safety net against any script that failed to self-delete.

   Note: tmuxinator self-deletes nothing and leaves a long-lived YAML; this generates ephemeral scripts per launch because the charter/prompt payload is dynamic and must not accumulate or leak between sessions.

**`menu.py`** — Interactive loop via `questionary`. `rich` renders a review table (directory / role / startup prompt per pane) before both save and launch, so the exact session is visible before anything spawns. Owns the create wizard, edit, delete, and role management.

**`main.py`** — Entry point. Ensures `config/` and the role seed exist, then enters the menu.

## Command / menu surface

| Action | Effect |
|---|---|
| Launch session | Pick profile → validate dirs + tooling → build `wt` command → exec |
| Create session | Wizard: name → layout → per-pane (dir, role, startup prompt) loop → review → save |
| Edit session | Pick profile → modify panes / layout / roles → review → save |
| Delete session | Pick profile → confirm → remove `profiles/<name>.json` |
| Manage roles | List / add / edit charters (built-ins included) |
| Quit | Exit process |

Startup-prompt presets: `continue` (Continue development on this project.), `workspace` (Check the workspace status for the current project.), `plan` (`/plan`), `custom` (free text).

Layout → `wt` flag: `vertical` = `-H` (stacked rows), `horizontal` = `-V` (side-by-side columns), `grid` = computed `-V`/`-H` + `--size` + `move-focus` (best-effort).

## Defaults policy

First run with zero configuration produces: a `config/` tree, a `roles.json` containing the four built-in charters, an empty `profiles/` directory, and a usable menu. The four charters are written so that a Backend-role pane, asked its role, describes backend work and declines to do system-architecture decisions — the defaults are "right" when each role's launched `claude` self-describes per its charter. This is asserted offline: the command builder test feeds a profile using a built-in role and asserts the emitted `--append-system-prompt` argument equals the seeded charter text exactly. No defaults require the user to write any charter before a first successful launch.

## Error handling

- Missing pane directory at launch → no terminal opens; the missing path(s) are listed; return to menu.
- `claude` not on `PATH` → pre-launch check fails with a fix hint (install / PATH); no terminal opens.
- `wt.exe` not found → same: explicit error, no launch attempt.
- Out-of-range or empty profile name → rejected at the wizard with the reason; nothing written.
- Corrupt `profiles/<name>.json` → skipped in the profile list with a one-line warning; menu stays usable; other profiles unaffected.
- Profile with zero panes → cannot be launched; flagged at save and at launch.
- A pane script that fails to self-delete → swept on the next launch's stale-script pass; never accumulates.

## Testing

- **Command builder, all layouts** — `Profile` literals (2-pane horizontal, 2-pane vertical, 4-pane grid) in, exact `wt.exe` arg list asserted out. Offline, no terminal. The grid case asserts pane count and presence of `--size`/`move-focus`, not pixel-exact geometry.
- **Charter fidelity** — pane with a built-in role and a charter containing `"` and `/`; assert the emitted `--append-system-prompt` argument equals the charter byte-for-byte and that here-string embedding in the generated `.ps1` round-trips.
- **Role omission** — pane with `role=None`; assert no `--append-system-prompt` segment is emitted.
- **Store round-trip** — write a `Profile`, read it back, assert equality; assert per-file layout on disk; assert corrupt-JSON file is skipped, not raised.
- **Validation** — existing vs missing directory; assert save warns-but-allows and launch hard-blocks with the offender listed; assert `which` failures for `claude`/`wt` are caught.
- **Live smoke test (manual)** — launch a real 2-pane profile and confirm two panes open in the correct directories with `claude` running. Per the compiled-target rule, completion is reported as "builds + command verified, needs your live test," not "done."
