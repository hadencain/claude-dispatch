# Claude Dispatch Hub

A Windows CLI launcher for multi-agent Claude Code sessions. You save a
**profile** describing how many panes you want, which project directory each
one opens in, what **role** (system-prompt charter) it plays, and what it
should do on startup. Launching that profile opens **one Windows Terminal
window**, split into panes, each `cd`'d into its directory and running
`claude` — so a whole multi-agent working session comes up in a single
command.

---

## Requirements

The tool itself is pure Python, but it drives external programs. You need:

| Requirement | Why | Check |
|-------------|-----|-------|
| **Python 3.14** (`python`) | runs the tool | `python --version` |
| **Windows Terminal** (`wt.exe`) | the window the panes open in | `wt.exe -v` |
| **Claude Code CLI** (`claude`) | what each pane actually runs | `claude --version` |
| **PowerShell** (`pwsh` *or* `powershell.exe`) | each pane is launched through it | `powershell -v` |
| `rich`, `questionary` | the menu UI | installed via requirements |
| `anthropic` | Dispatch from queue triage (optional) | installed via requirements |

`pwsh` (PowerShell 7) is preferred but **not required** — the launcher falls
back to the built-in `powershell.exe` (5.1) automatically. The only hard
requirement is that *one* of them exists.

The launch **preflight will tell you** if `wt.exe`, `claude`, or a PowerShell
is missing, so you don't have to verify all of this by hand.

---

## Install

```powershell
cd C:\Users\haden\documents\ship\src\projectHub
python -m pip install -r requirements.txt
```

---

## Run

```powershell
cd C:\Users\haden\documents\ship\src\projectHub
python -m dispatch_hub
```

> **Run it from the project directory.** Config is stored under a `config/`
> folder *relative to your current directory*, so launching from elsewhere
> creates a separate, empty config. Stick to one working directory.

You get an arrow-key menu:

```
? Claude Dispatch Hub
> Launch session
  Create session
  Dispatch from queue
  Delete session
  Manage roles
  Quit
```

Arrow keys move, **Enter** selects, **Ctrl+C / Esc** cancels the current
prompt (it backs you out cleanly — it won't crash or save half a profile).

---

## Quick start

1. **Create session** — build and save a profile (walkthrough below).
2. **Launch session** — pick it; a Windows Terminal window opens with your panes.

That's the whole loop. Everything else is editing.

---

## Creating a profile

Choose **Create session** and answer the prompts:

1. **Profile name** — letters, digits, dot, dash, underscore only (no spaces
   or slashes). Must be unique. This becomes the JSON filename.
2. **Layout** — how the panes are arranged in the window:

   | Layout | Arrangement | Behaviour |
   |--------|-------------|-----------|
   | `vertical` | stacked rows (top to bottom) | exact |
   | `horizontal` | side-by-side columns (left to right) | exact |
   | `grid` | roughly even grid | **best-effort** — geometry is approximate and may need tuning |

3. **Per pane**, repeated until you say stop:
   - **Project directory** — a searchable list of projects discovered in your
     workspace (type to filter), or pick **✎ Type a path manually** to enter any
     path. The folder is validated at launch, not here, so a typo surfaces when
     you try to run it.
   - **Role** — `(none)` or one of your roles. The role's charter is injected
     into that pane's Claude via `--append-system-prompt`.
   - **Startup prompt** — what the pane does the moment Claude starts. Each
     preset shows its resolved text inline so you know what it sends before you
     pick it (see presets below).
   - **Next?** — add another pane, or finish to review.
4. **Review** — a table of the profile is shown. Save it to
   `config/profiles/<name>.json`, add another pane, or discard.

**Backing up:** every menu has a **← Back** option that steps *back one field*
so you can fix the last answer without throwing away the whole profile. On the
text fields (profile name, manual path, custom prompt), leave the input **blank**
to go back. Backing out of the profile name returns you to the main menu.
(Esc also works as Back where your terminal supports it.)

The project list is scanned from your workspace root (the Ship workspace by
default). Override it by creating `config/settings.json` with
`{ "workspace_root": "C:/some/other/root" }`.

### Startup prompt presets

| Preset | Sends to Claude |
|--------|-----------------|
| `continue` | `Continue development on this project.` |
| `workspace` | `Check the workspace status for the current project.` |
| `plan` | `/plan` |
| `custom` | whatever free text you type |

Presets are resolved to literal text **at save time** — the saved profile
stores the final string, not the preset name.

---

## Launching a session

Choose **Launch session** and pick a profile. Before opening anything, the
tool runs a **preflight**:

- the profile has at least one pane,
- required tools are on PATH (`wt.exe`, `claude`, a PowerShell),
- every pane's directory actually exists.

If any check fails it prints exactly what's wrong and returns to the menu —
nothing launches. If all pass, it shows the profile table and asks to confirm.
On confirm:

- one **Windows Terminal** window opens, split per your layout;
- each pane `cd`s into its directory and runs `claude`;
- panes with a role get that role's charter via `--append-system-prompt`;
- panes with a startup prompt get it as Claude's first input.

**Pane titles** are chosen as: explicit pane title → role name → directory
folder name.

---

## Dispatch from queue

Reads a Markdown work-queue file, lets you multi-select items from the
`## Queued` section, sends them to Claude for triage (role, directory, and
startup prompt assignment), then launches the result as a session. Dispatched
items are moved to `## In Progress` in the queue file after launch.

**Setup:**

1. Set `work_queue_path` in `config/settings.json` to the absolute path of
   your Markdown queue file.
2. Optionally set `triage_model` in settings (default: `claude-sonnet-4-6`).

**API key:** the first time you dispatch without a key configured, the tool
prompts you to paste your Anthropic key (input is masked) and saves it to
`config/settings.json` — you are not asked again. `config/settings.json` is
gitignored, so the key never enters the repo. You can also set the
`ANTHROPIC_API_KEY` environment variable, which overrides the saved key.

If the queue path is missing, the action prints a one-line hint and returns to
the menu. Items with an unresolved directory (not found in the discovered
project list) block launch until fixed.

---

## Roles

Roles are reusable **charters** — system-prompt text that shapes how a pane's
Claude behaves. Ten are built in:

- **Architect** — system design, boundaries, trade-offs; reviews rather than implements.
- **Backend** — data models, business logic, APIs, persistence, their tests.
- **Frontend** — UI, components, layout, state, user-facing behaviour.
- **QA** — testing, edge cases, regressions, verification.
- **Security** — auth, attack surfaces, dependency risk, secure defaults.
- **Performance** — latency, throughput, resource usage, profiling, bottlenecks.
- **Data** — schemas, migrations, storage strategy, data quality, lifecycle.
- **DevOps** — deployment, environments, automation, observability, reliability.
- **Docs** — documentation, onboarding, developer experience, knowledge transfer.
- **Research** — investigation, feasibility, trade-offs, dependency evaluation.

### Managing roles

Choose **Manage roles** for a live editor:

- **View a charter** — show a role's full charter text (the overview table
  truncates long charters; this shows the whole thing).
- **Edit a charter** — change any role's charter text.

Changes are written immediately to `config/roles.json`. You can also edit that
file by hand if you prefer — including adding your own roles to the array.

---

## Where things are stored

All under `config/` in the directory you run from (all git-ignored):

```
config/
  profiles/
    <name>.json      # one file per saved profile
  roles.json         # your roles (seeded with the ten built-ins on first run)
  .launch/           # generated per-pane PowerShell scripts (scratch)
```

### Profile file format

```json
{
  "name": "sprint",
  "layout": "horizontal",
  "panes": [
    { "directory": "C:/work/api", "role": "Backend",
      "startup_prompt": "Continue development on this project.", "title": null },
    { "directory": "C:/work/ui",  "role": "Frontend",
      "startup_prompt": "/plan", "title": null }
  ],
  "created": "2026-06-22T...Z",
  "modified": "2026-06-22T...Z"
}
```

Profiles are plain JSON and safe to hand-edit. A corrupt profile file is
skipped (with a warning) rather than crashing the listing.

---

## How a launch works under the hood

For each pane the tool writes a small PowerShell script into `config/.launch/`
that:

1. deletes itself (so no scratch is left behind once it starts),
2. `Set-Location`s into the pane's directory,
3. reconstructs the charter and startup prompt from **base64** (this keeps any
   characters — quotes, slashes, newlines — intact and injection-safe),
4. runs `claude` with the appropriate flags.

It then builds a single `wt.exe` command that opens the window and splits it,
pointing each pane at its script, and runs it. Stale `.launch/*.ps1` scripts
are swept at the start of every launch, so the folder stays clean.

You never interact with these scripts directly — they're an implementation
detail — but that's what's happening when a session comes up.

---

## Troubleshooting

**"Missing tools on PATH: ..."** — install/expose whatever it names.
`wt.exe` = Windows Terminal, `claude` = Claude Code CLI, `powershell` = no
PowerShell found at all (very unusual on Windows).

**The window opens but panes close instantly / Claude doesn't start** — open a
pane manually and run `claude` there to see the real error (auth, not on PATH,
etc.). The panes use `-NoExit`, so the shell stays open even if `claude` exits,
which lets you read any message.

**Grid layout looks uneven** — expected. `grid` geometry is best-effort; the
pane *count* is always right but sizing is approximate. `vertical` and
`horizontal` are exact if you want predictable splits.

**Nothing happens after I confirm launch** — confirm `wt.exe` runs on its own
(`wt.exe` in a terminal should open a window). If Windows Terminal isn't
installed, install it from the Microsoft Store.

**My profile/role edits vanished** — make sure you're running from the same
directory every time; `config/` is relative to your working directory.

---

## Command reference

| Action | What it does |
|--------|--------------|
| `python -m dispatch_hub` | start the interactive menu |
| Launch session | preflight + open a saved profile as a live session |
| Create session | build and save a new profile |
| Dispatch from queue | triage work-queue items and launch as a session |
| Delete session | remove a saved profile |
| Manage roles | view / edit role charters |
| Quit | exit |

| File | Purpose |
|------|---------|
| `config/profiles/<name>.json` | saved profiles (hand-editable) |
| `config/roles.json` | role charters (hand-editable) |
| `config/settings.json` | workspace root, queue path, API key, triage model |
| `config/.launch/` | generated launch scripts (scratch, auto-cleaned) |
