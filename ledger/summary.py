"""Compact, one-shot usage glance for embedding in other tools (e.g. the
dispatch hub menu). Reads Claude Code transcripts, returns a small rich panel.

Pure of the resources/psutil layer — importing this never pulls in psutil.
Every failure path returns a quiet panel instead of raising, so a host tool can
render it unconditionally.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .aggregate import Aggregator
from .cache import ParseCache
from .format import bar, short_project, units
from .transcripts import (default_projects_root, iter_transcript_files,
                          parse_file, project_label)


def _default_cache_path() -> Path:
    return Path.home() / ".ledger" / "parse-cache.json"


def _scan(root: Path, cache_path: Path) -> Aggregator:
    agg = Aggregator()
    cache = ParseCache(cache_path)
    for file in iter_transcript_files(root):
        for event in cache.get_or_parse(file, project_label(file), parse_file):
            agg.add(event)
    cache.save()
    return agg


def usage_panel(top_projects: int = 5, root: Path | None = None,
                cache_path: Path | None = None, now: datetime | None = None) -> Panel:
    """A compact 'Ledger · usage' panel: today/this-week/all-time usage units
    plus the top projects by share. Never raises — returns a quiet panel on any
    failure or when there's no data yet."""
    root = root or default_projects_root()
    cache_path = cache_path or _default_cache_path()
    now = now or datetime.now(timezone.utc)

    try:
        agg = _scan(Path(root), Path(cache_path))
        totals = agg.totals(now.date(), now, 600)
        projects = agg.projects(now.date())
    except Exception:
        return Panel(Text("usage data unavailable", style="dim"), title="Ledger · usage",
                     expand=False)

    if totals.all_time <= 0:
        return Panel(Text("No Claude usage data yet.", style="dim"),
                     title="Ledger · usage", expand=False)

    header = Text(
        f"today {units(totals.today)}   this-week {units(totals.this_week)}   "
        f"all-time {units(totals.all_time)} units",
        style="bold",
    )

    grand = sum(p.all_time for p in projects) or 1.0
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="left")
    table.add_column(justify="right")
    table.add_column(justify="left")
    table.add_column(justify="right")
    for p in projects[:top_projects]:
        frac = p.all_time / grand
        table.add_row(
            short_project(p.project), f"{frac * 100:4.0f}%",
            bar(frac, width=10), units(p.all_time),
        )

    hint = Text("run `python -m ledger` for the live dashboard", style="dim")
    return Panel(Group(header, table, hint), title="Ledger · usage", expand=False)
