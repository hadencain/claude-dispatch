# Claude Dispatch Hub

Windows CLI launcher for multi-agent Claude Code sessions via Windows Terminal.

- Run: `python -m dispatch_hub`
- Test: `python -m pytest tests/ -v`
- Spec: `docs/superpowers/specs/2026-06-21-claude-dispatch-hub-design.md`

`launcher.py` is the launch core — pure command construction, no I/O beyond writing scripts and `subprocess`. Do not import `menu`/`roles` into it.

## Ledger (Local AI Resource Governor)

Standalone read-only monitor of all Claude Code sessions on this machine — live token
usage, dollar cost, and CPU/RAM/GPU. Does not import `dispatch_hub`.

- Run: `python -m ledger`
- One-shot snapshot: `python -m ledger --once`
- Test: `python -m pytest tests/ledger/ -v`
- Spec: `docs/superpowers/specs/2026-06-24-ledger-design.md`
- Deps: `rich`, `psutil` (`pip install -r ledger/requirements.txt`). GPU via `nvidia-smi` subprocess (no dep).
- Config/cache/alerts under `~/.ledger/`.
