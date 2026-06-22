from __future__ import annotations

import math
import os
import re
import subprocess
from pathlib import Path

from .models import Pane, Profile

LAUNCH_DIR_NAME = ".launch"

# layout name -> wt split-pane divider flag for simple layouts
_SIMPLE_FLAG = {"vertical": "-H", "horizontal": "-V"}


def _pane_title(pane: Pane) -> str:
    if pane.title:
        return pane.title
    if pane.role:
        return pane.role
    base = os.path.basename(pane.directory.rstrip("/\\"))
    return base or pane.directory


def _grid_actions(n: int) -> list[tuple[str, str | None, list[str]]]:
    """Best-effort even grid. Pane count is exact; geometry is approximate
    and may need tuning during the live smoke test."""
    cols = math.ceil(math.sqrt(n))
    base, extra = divmod(n, cols)
    col_counts = [base + (1 if c < extra else 0) for c in range(cols)]

    actions: list[tuple[str, str | None, list[str]]] = [("pane", None, [])]
    # first pane of each subsequent column, left to right
    for c in range(1, cols):
        size = round(1.0 / (cols - c + 1), 3)
        actions.append(("pane", "-V", ["--size", str(size)]))
    # return focus to leftmost column
    for _ in range(cols - 1):
        actions.append(("focus", "left", []))
    # fill each column downward
    for c in range(cols):
        if c > 0:
            actions.append(("focus", "right", []))
        for r in range(col_counts[c] - 1):
            size = round(1.0 / (col_counts[c] - r), 3)
            actions.append(("pane", "-H", ["--size", str(size)]))
    return actions


def _layout_actions(layout: str, n: int) -> list[tuple[str, str | None, list[str]]]:
    if n <= 0:
        return []
    if layout == "grid":
        return _grid_actions(n)
    if layout not in _SIMPLE_FLAG:
        raise ValueError(f"unknown layout: {layout}")
    flag = _SIMPLE_FLAG[layout]
    actions: list[tuple[str, str | None, list[str]]] = [("pane", None, [])]
    for _ in range(n - 1):
        actions.append(("pane", flag, []))
    return actions


def build_command(profile: Profile, script_paths: list[str]) -> list[str]:
    if not profile.panes:
        raise ValueError("profile has no panes")
    actions = _layout_actions(profile.layout, len(profile.panes))
    subs: list[list[str]] = []
    pane_idx = 0
    for kind, flag, extra in actions:
        if kind == "focus":
            subs.append(["move-focus", flag or "left"])
            continue
        pane = profile.panes[pane_idx]
        script = script_paths[pane_idx]
        if pane_idx == 0:
            tokens = ["new-tab"]
        else:
            tokens = ["split-pane"] + ([flag] if flag else []) + list(extra)
        tokens += ["-d", pane.directory, "--title", _pane_title(pane),
                   "pwsh", "-NoExit", "-File", script]
        subs.append(tokens)
        pane_idx += 1

    cmd = ["wt.exe"]
    for j, sub in enumerate(subs):
        if j:
            cmd.append(";")
        cmd += sub
    return cmd


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name) or "profile"


def render_pane_script(pane: Pane, charter: str | None) -> str:
    dir_lit = pane.directory.replace("'", "''")
    lines = [
        "Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue",
        f"Set-Location -LiteralPath '{dir_lit}'",
    ]
    has_prompt = bool(pane.startup_prompt)
    if has_prompt:
        lines += ["$prompt = @'", pane.startup_prompt, "'@"]
    if charter is not None:
        lines += ["$charter = @'", charter, "'@"]

    call = "claude"
    if charter is not None:
        call += " --append-system-prompt $charter"
    if has_prompt:
        call += " $prompt"
    lines.append(call)
    return "\r\n".join(lines) + "\r\n"


def write_pane_scripts(profile: Profile, charters: dict[str, str],
                       work_dir: Path) -> list[Path]:
    work_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    safe = _safe_name(profile.name)
    for i, pane in enumerate(profile.panes):
        charter = charters.get(pane.role) if pane.role else None
        content = render_pane_script(pane, charter)
        p = work_dir / f"{safe}_{i}.ps1"
        p.write_text(content, encoding="utf-8")
        paths.append(p)
    return paths


def sweep_stale_scripts(work_dir: Path) -> None:
    if not work_dir.exists():
        return
    for f in work_dir.glob("*.ps1"):
        try:
            f.unlink()
        except OSError:
            pass


def launch(profile: Profile, charters: dict[str, str], work_dir: Path,
           runner=subprocess.run):
    sweep_stale_scripts(work_dir)
    paths = write_pane_scripts(profile, charters, work_dir)
    cmd = build_command(profile, [str(p) for p in paths])
    return runner(cmd)
