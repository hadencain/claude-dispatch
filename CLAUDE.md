# Claude Dispatch Hub

Windows CLI launcher for multi-agent Claude Code sessions via Windows Terminal.

- Run: `python -m dispatch_hub`
- Test: `python -m pytest tests/ -v`
- Spec: `docs/superpowers/specs/2026-06-21-claude-dispatch-hub-design.md`

`launcher.py` is the launch core — pure command construction, no I/O beyond writing scripts and `subprocess`. Do not import `menu`/`roles` into it.
