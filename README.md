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
   - **Project directory** — an existing folder the pane opens in (validated at
     launch, not here, so a typo surfaces when you try to run it).
   - **Role** — `(none)` or one of your roles. The role's charter is injected
     into that pane's Claude via `--append-system-prompt`.
   - **Startup prompt** — what the pane does the moment Claude starts (see
     presets below).
   - **Add another pane?** — yes to add more, no to finish.
4. **Review** — a table of the profile is shown. Confirm to save it to
   `config/profiles/<name>.json`.

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

## Roles

Roles are reusable **charters** — system-prompt text that shapes how a pane's
Claude behaves. Four are built in:

- **Architect** — system design, boundaries, trade-offs; reviews rather than implements.
- **Backend** — data models, business logic, APIs, persistence, their tests.
- **Frontend** — UI, components, layout, state, user-facing behaviour.
- **QA** — testing, edge cases, regressions, verification.

### Managing roles

Choose **Manage roles** for a live editor:

- **View a charter** — show a role's full charter text (the overview table
  truncates long charters; this shows the whole thing).
- **Edit a charter** — change any role's charter text (built-ins included).
- **Add a role** — create a new custom role with its own charter.
- **Import from JSON file** — bulk-add roles from a JSON file. Point it at a
  file containing a single role object or an array of them; matching names are
  updated, new names are added. Imported roles are always custom. This is how
  you load charters generated elsewhere (see below).
- **Delete a custom role** — remove a role you added. Built-in roles are
  **delete-protected** (you can edit their charters but not remove them).

Changes are written immediately to `config/roles.json`. You can also edit that
file by hand if you prefer.

### Generating roles with another AI, then importing

`docs/role-authoring-prompt.md` is a portable prompt you can paste into any AI
model. It defines the charter structure this system expects and asks the model
to emit a ready-to-import JSON array:

```json
[
  { "name": "Security", "charter": "You are the Security reviewer. Focus on ...", "builtin": false }
]
```

Save that array to a file, then **Manage roles → Import from JSON file** to load
it in one step.

---

## Where things are stored

All under `config/` in the directory you run from (all git-ignored):

```
config/
  profiles/
    <name>.json      # one file per saved profile
  roles.json         # your roles (seeded with the four built-ins on first run)
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
| Delete session | remove a saved profile |
| Manage roles | add / edit / delete role charters |
| Quit | exit |

| File | Purpose |
|------|---------|
| `config/profiles/<name>.json` | saved profiles (hand-editable) |
| `config/roles.json` | role charters (hand-editable) |
| `config/.launch/` | generated launch scripts (scratch, auto-cleaned) |
