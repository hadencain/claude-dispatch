# Ledger — Roadmap / Follow-up

_Status: 2026-06-27. On `main`, pushed to github.com/hadencain/claude-dispatch._

A place to pick Ledger back up later. Read this first if you're cold.

## What Ledger is

Standalone read-only package `ledger/` (sibling to `dispatch_hub`; **never imports
it** — the app imports the library, never the reverse). Reads Claude Code session
JSONL transcripts (`~/.claude/projects/*/*.jsonl`) and reports weighted **usage
units** per session / project / day — deliberately *not* dollars (notional on a
subscription). Surfaces:

- `python -m ledger` — live TUI (rich.Live refresh loop)
- `python -m ledger --once` — one-shot frame
- a compact panel in the `dispatch_hub` menu (under the splash)

## Done

- **Usage units**: `out×5, in×1, cache-read×0.1, cache-write-5m×1.25, cache-write-1h×2`,
  model-agnostic (output is exactly 5× input on every Claude model, so the rate
  factors out). Headline = today / this-week / all-time; projects shown by % share.
- **Dispatch-hub footer** (`ledger.summary.usage_panel`) — guarded, psutil-free import path.
- **Resource panel auto-gated** (`config.show_resources` = auto/always/never): hidden
  during API-only sessions (flat zero), shown when GPU busy or an AI process ≥25% CPU.
- **Trimmed**: removed dormant dollar code (`cost`/`RATES`/`CostBreakdown`) and the
  always-blank per-process→project attribution column.
- ~110 tests pass; `--once` verified against real history.

## Architecture (modules)

`models` (UsageEvent) · `pricing` (usage_units) · `transcripts` (parse JSONL) ·
`aggregate` (rollups + **requestId dedup**) · `cache` (parse cache, size+mtime keyed) ·
`watch` (byte-offset tail) · `resources` (nvidia-smi subprocess + psutil) ·
`budget` (thresholds — **inert until step 4**) · `config` · `notify` (toast/log) ·
`format` (shared formatters) · `summary` (dispatch panel) · `tui` · `__main__`.

## Open / next steps

### Step 4 — Rate-limit governor pivot (the substantive one)

The usage-units number isn't actionable without a limit to measure against. Anchor
`this_week` to the **Max weekly cap** (user-set / calibrated once — it is *not* in the
transcripts). This **revives the already-built but inert** budget→crossing→notify
pipeline rather than writing new machinery:

- `budget.py`, `notify.py`, `CrossingTracker` exist and are wired in `__main__`, but
  budgets default to `0` (off) → `evaluate()` returns OK → alerts never fire today.
- Add `weekly_usage_budget` to config; feed `this_week` into `evaluate()`.
- Show: % of weekly cap consumed, **burn rate** (units/hr), projected time-to-cap,
  reset countdown. Alert as the cap approaches.

### Step 5 — Dispatch forecast fusion

Before dispatching a queue of agents, show that dispatch's projected usage vs the
remaining weekly budget ("this dispatch ≈ X% of your remaining week") — governance at
the moment of spending, not just retrospective. `dispatch_hub` already imports
`ledger`; needs a per-project/historical usage estimate to forecast from.

### Step 6 — Live TUI verification debt

`python -m ledger` (the live `rich.Live` loop) has **never been user-tested** — only
`--once`. Run it, confirm the refresh and the budget-alert path. Could harbor a
refresh-loop bug we've never exercised.

## Deferred minors

- `message.id` as a secondary dedup key (spec mentioned it; `requestId` is present on
  100% of real lines, so it's belt-and-suspenders).
- `scripts/create-shortcut.ps1` has an uncommitted local change (Ledger.lnk rename),
  intentionally left out of git.

## Key facts for a cold start

- Data: `~/.claude/projects/<encoded-dir>/<uuid>.jsonl`; assistant lines carry
  `message.usage`; **dedup on `requestId`** (Claude Code re-logs usage across iterations).
- Config / cache / alerts live under `~/.ledger/`.
- Run with `python` (not `python3`). Deps: `rich`, `psutil`. GPU via `nvidia-smi` subprocess.
- Tests: `python -m pytest tests/ledger/ -v`.
