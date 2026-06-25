# Ledger — Local AI Resource Governor

**Status:** Design / approved for planning
**Date:** 2026-06-24
**Repo:** `src/claude-dispatch` (new sibling package `ledger/`, standalone — does **not** import `dispatch_hub`)

## What it is

A read-only terminal dashboard that watches every Claude Code session on this
machine and shows, live, what they cost (tokens → dollars) and what they consume
(CPU / RAM / GPU). It reads Claude Code's own session transcripts off disk — no
API calls, no instrumentation of the sessions themselves. Budgets make overspend
loud; it cannot enforce caps (an API client can't cap Anthropic's meter), so
"governor" here means *visibility + alerting*, not control.

It is launched and read independently of `claude-dispatch`. Dispatch keeps
launching sessions; Ledger watches all of them (and any session dispatch didn't
launch) the same way.

### Honest scope notes (decided during brainstorming)

- **GPU/CPU for API-backed sessions reads near-zero.** A `claude` process waiting
  on a streaming response uses trivial local CPU and no GPU. The resource panel
  earns its place by lighting up for *local* inference (Ollama, ComfyUI, a torch
  script) — it answers "what on this machine is eating my AI resources," which is
  broader than just Claude. This is intentional, not a bug.
- **GPU via `nvidia-smi` subprocess, not `pynvml`.** `nvidia-smi` is already
  present (verified: `GTX 1650, 4096 MiB`), emits stable CSV, and survives driver
  changes. `pynvml` is a fragile binding across driver/Turing versions. Absent
  `nvidia-smi` → the GPU panel degrades to "no NVIDIA GPU".
- **PID↔session attribution is best-effort and labeled as such.** There is no
  hard link from a `node`/`claude` process to a specific transcript; we match on
  `process.cwd()` → project dir. Ambiguous cases are shown without attribution
  rather than guessed.

## Data source (verified on disk)

Claude Code writes one JSONL transcript per session at:

```
~/.claude/projects/<encoded-project-path>/<session-uuid>.jsonl
```

(70 project dirs currently present.) The encoded dir name is the project path
with separators replaced by `-`; it is used as the **project key / display
label** — exact path reconstruction is lossy and not required.

Each assistant line carries everything cost needs (verified schema):

```jsonc
{
  "type": "assistant",
  "sessionId": "38b4eab1-…",
  "timestamp": "2026-06-25T00:51:43.924Z",
  "requestId": "req_011CcP4…",          // dedup key — see below
  "message": {
    "model": "claude-opus-4-8",
    "usage": {
      "input_tokens": 9443,
      "cache_read_input_tokens": 13340,
      "cache_creation_input_tokens": 9225,
      "output_tokens": 548,
      "cache_creation": {                 // the price-relevant split
        "ephemeral_5m_input_tokens": 0,
        "ephemeral_1h_input_tokens": 9225
      },
      "server_tool_use": { "web_search_requests": 0, "web_fetch_requests": 0 }
    }
  }
}
```

**Two correctness traps, handled in `transcripts.py`:**

1. **Dedup on `requestId`** (+ `message.id` when present). Claude Code re-logs the
   same usage across streaming iterations; counting every assistant line
   double-counts. One usage record per unique request.
2. **Cache-write price split.** `cache_creation_input_tokens` is *not* a single
   rate — `ephemeral_5m` writes cost `1.25×` input, `ephemeral_1h` writes cost
   `2×` input. Use the `cache_creation` sub-object; fall back to treating the
   lump `cache_creation_input_tokens` as 5m only if the sub-object is absent
   (older transcripts).

## Architecture

New package `ledger/`, pure-Python + `rich` (TUI) + `psutil` (per-process). GPU is
a `nvidia-smi` subprocess (no dependency). Each module has one job and is testable
in isolation.

| Module | Responsibility | Deps |
|---|---|---|
| `transcripts.py` | Locate `~/.claude/projects/*/*.jsonl`; parse lines; extract assistant `usage` events; **dedup on requestId**. Yields typed `UsageEvent`. | stdlib |
| `pricing.py` | Model-id → rate table; `cost(event) -> CostBreakdown`. Unknown model → `unpriced` flag, never silent $0. | — |
| `aggregate.py` | Pure folds over the event stream → `SessionRollup`, `ProjectRollup`, `DayRollup`, `Totals` (all-time / today / this-month). | transcripts, pricing |
| `cache.py` | On-disk parse cache keyed by `(path, size, mtime)` so the full-history scan only re-parses changed files. First run parses all; later runs near-instant. | — |
| `watch.py` | Tail. Per-file byte offset; each tick read only appended bytes + detect new files. Polling (~1.5 s), not a filesystem watcher (robust on Windows/OneDrive). | transcripts |
| `resources.py` | Per-tick system snapshot: GPU (nvidia-smi CSV), system CPU/RAM (psutil), AI-process table (psutil, filtered), best-effort cwd→project attribution. | psutil |
| `budget.py` | Read thresholds from config; evaluate rollups → `ok / warn / over`. Edge-triggered crossing detection. | aggregate |
| `notify.py` | Windows toast on a budget *crossing* (once per crossing, not per tick). | budget |
| `tui.py` | `rich.Live` render loop; assembles all panels. | everything |
| `config.py` | Load/create `~/.ledger/config.json`. | — |
| `__main__.py` | Wire: cold scan w/ progress → build rollups → start watch + resource loops → drive TUI. | all |

### Data flow

```
cold start: discover transcripts ─▶ cache.load() ─▶ parse changed files only
                                                          │
                                                          ▼
                                              aggregate ─▶ Rollups ──┐
                                                                     ▼
tick (~1.5s): watch.poll() ─▶ new UsageEvents ─▶ aggregate.update() ─▶ Rollups ─▶ budget.evaluate()
              resources.snapshot() ─────────────────────────────────────────────┐         │
                                                                                 ▼         ▼
                                                                         tui.render()   notify (on crossing)
```

## Pricing table (`pricing.py`)

Per-MTok rates, maintained manually (source of truth: the claude-api skill
reference). Cache rates derive from the input rate by multiplier, so the table
stores only input/output and computes the rest:

| Model id | input $/MTok | output $/MTok |
|---|---|---|
| `claude-fable-5` | 10.00 | 50.00 |
| `claude-opus-4-8` | 5.00 | 25.00 |
| `claude-opus-4-7` | 5.00 | 25.00 |
| `claude-opus-4-6` | 5.00 | 25.00 |
| `claude-opus-4-5` | 5.00 | 25.00 |
| `claude-sonnet-4-6` | 3.00 | 15.00 |
| `claude-sonnet-4-5` | 3.00 | 15.00 |
| `claude-haiku-4-5` | 1.00 | 5.00 |

Derived cache rates per model: `cache_read = 0.1 × input`, `cache_write_5m =
1.25 × input`, `cache_write_1h = 2 × input`. Optional server-tool extra:
web-search billed per call (configurable constant, default `$10 / 1000`), shown
separately; web-fetch treated as free. Unknown model id → row rendered with an
`unpriced` badge and excluded from dollar totals (tokens still counted), so a
newly-released model surfaces loudly instead of undercounting the bill.

`cost(event)` returns a `CostBreakdown` (input / output / cache-read /
cache-write-5m / cache-write-1h / web, plus total) so the TUI can show where the
money goes — cache reads vs fresh input is the most actionable split.

## Resources panel (`resources.py`)

Per tick:

- **GPU** — `nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits` → util %, VRAM used/total, temp. Per-PID VRAM via `--query-compute-apps=pid,used_memory`. No `nvidia-smi` → panel shows "no NVIDIA GPU".
- **System** — `psutil.cpu_percent()`, `psutil.virtual_memory()`.
- **AI-process table** — `psutil.process_iter`, filtered to a configurable name/cmdline list (default: `node`/`claude`, `python`, `ollama`, plus anything the user adds). Each row: name · PID · CPU% · RAM(RSS) · VRAM (joined by PID from the compute-apps query) · attributed project.
- **Attribution** — `proc.cwd()` matched against known project dirs; if a match has a recently-written transcript, tag the row with that project. No match → blank. Labeled best-effort in the UI.

No resource thresholds/alerts in v1 — budgets are dollars only (keeps "governor"
meaning one thing). Resource monitoring is observability.

## TUI layout (`tui.py`)

One `rich.Live` screen, panels stacked top→bottom:

```
ledger
  all-time $312.40   today $8.21   this-month $44.10   active 3
┌ Active sessions ───────────────────────────────────────────────────┐
│ 38b4ea  claude-dispatch   opus-4-8   in 1.2M  out 24K  cache 8.1M   │
│         $1.04   ▓▓▓▓▓▓░░  last 12s                                  │
└────────────────────────────────────────────────────────────────────┘
┌ Projects (all-time / today) ──┐ ┌ Last 14 days ─────────────────────┐
│ claude-dispatch  $40.2 / $1.0 │ │ ▁▂▅▇▃▂▁▄█▆▃▂▁▂  $8.21 today        │
└───────────────────────────────┘ └───────────────────────────────────┘
┌ Resources ─────────────────────────────────────────────────────────┐
│ CPU 14%  RAM 9.2/32G  GPU 0%  VRAM 0/4096M  41°C                    │
│ node    14820  3.1%  412M   —      claude-dispatch                  │
│ python  9233   88%   2.1G   1840M  terrain-gen   (local inference)  │
└────────────────────────────────────────────────────────────────────┘
  budget: today $8.21 / $20.00 ok   ·   1 unpriced model   ·   q quit
```

- **Header** — all-time / today / this-month dollars + active-session count.
- **Active sessions** — sessions with activity in the last N minutes; live token
  counters, dollar cost, a budget bar (green→amber→red per `warn_ratio`/over),
  last-activity age. Sorted most-recent-first.
- **Projects** — top-N by all-time dollars, with today alongside.
- **History** — last 14 days, dollars/day + a sparkline.
- **Resources** — gauges + the AI-process table.
- **Footer** — budget status, unpriced-model count, `q` to quit.

## Budgets & config (`~/.ledger/config.json`)

```jsonc
{
  "daily_usd_budget": 20.0,
  "per_session_usd_budget": 5.0,
  "warn_ratio": 0.8,            // amber at 80% of a budget
  "notify": true,              // Windows toast on crossing
  "ai_process_names": ["node", "claude", "python", "ollama"],
  "web_search_usd_per_1k": 10.0,
  "history_days": 14
}
```

Read at startup; no in-app editing in v1. `budget.evaluate()` returns a per-target
state (`ok`/`warn`/`over`) for the day total and each active session; crossings
are edge-triggered so a toast fires once when a budget is first exceeded, not every
tick.

## Cold-start performance

Worst case ~hundreds of JSONL files across 70 project dirs. First launch parses
all once behind a progress line; `cache.py` stores per-file parsed results keyed
by `(path, size, mtime)`. Subsequent launches re-parse only changed/new files, so
"full history" stays affordable. Live tailing reads only appended bytes via the
per-file offset in `watch.py`.

## Testing strategy

- `transcripts.py` — fixture JSONL incl. duplicate `requestId` lines (dedup),
  the `ephemeral_5m`/`ephemeral_1h` split, an older lump-cache line, a malformed
  line (skipped, not fatal), and a non-assistant line (ignored).
- `pricing.py` — every table model; cache-multiplier math; unknown model →
  `unpriced` + excluded from dollars; web-search extra.
- `aggregate.py` — folds produce correct session/project/day/total rollups;
  incremental `update()` matches a full re-fold.
- `cache.py` — unchanged file served from cache; changed `mtime`/`size` re-parsed.
- `watch.py` — appended bytes only; new file detected; truncation/rotation safe.
- `resources.py` — `nvidia-smi` CSV parsing (incl. absent-binary fallback) via a
  fake subprocess runner; psutil access behind a seam so it's mockable.
- `budget.py` — ok/warn/over thresholds; edge-triggered crossing fires once.

`tui.py`, `notify.py`, and live `nvidia-smi`/psutil are thin I/O shells over tested
pure logic — covered by a manual smoke run, not unit tests.

## Dependencies added

- `psutil` (per-process CPU/RAM + cwd). New dep — log in the project's dependency
  record per repo convention.
- `rich` (TUI). New dep.
- GPU is `nvidia-smi` via `subprocess` — no dependency.

## Explicitly out of scope (v1)

- Resource/GPU budget thresholds (dollars only).
- Killing or throttling sessions (read-only by design).
- Web dashboard (TUI is the chosen surface).
- Historical charts beyond the day sparkline.
- Multi-machine aggregation.
```