# ledger/__main__.py
from __future__ import annotations

import argparse
import io
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.live import Live

from .aggregate import Aggregator
from .budget import CrossingTracker, evaluate
from .cache import ParseCache
from .config import Config, default_config_path, load
from .notify import Notifier
from .resources import ai_processes, gpu_processes, gpu_snapshot, system_snapshot
from .transcripts import (default_projects_root, iter_transcript_files,
                          parse_file, project_label)
from .tui import DashboardState, render_dashboard
from .watch import Watcher

try:
    import psutil as _psutil
except ImportError:
    _psutil = None

_TICK_SECONDS = 1.5


def build_state(agg: Aggregator, config: Config, now: datetime,
                run=subprocess.run, ps=_psutil) -> DashboardState:
    gpu = gpu_snapshot(run=run)
    gpu_pids = gpu_processes(run=run)
    system = system_snapshot(ps=ps)
    project_dirs: set[str] = set()  # v1: per-process project attribution is best-effort; left empty here (see spec). Renders "—".
    procs = ai_processes(config.ai_process_names, project_dirs, gpu_pids, ps=ps)
    today = now.date()
    totals = agg.totals(today, now, config.active_window_seconds)
    report = evaluate(
        totals.today,
        agg.session_usage(), config.daily_usage_budget,
        config.per_session_usage_budget, config.warn_ratio,
    )
    return DashboardState(
        totals=totals,
        sessions=agg.active_sessions(now, config.active_window_seconds),
        projects=agg.projects(today),
        day_usage=agg.day_usage(),
        gpu=gpu, system=system, procs=procs, budget=report,
        history_days=config.history_days,
    )


def _cold_scan(agg: Aggregator, cache: ParseCache, root: Path) -> None:
    for file in iter_transcript_files(root):
        for event in cache.get_or_parse(file, project_label(file), parse_file):
            agg.add(event)
    cache.save()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ledger")
    parser.add_argument("--once", action="store_true",
                        help="render a single frame and exit")
    args = parser.parse_args(argv)

    config = load(default_config_path())
    root = default_projects_root()
    cache = ParseCache(Path.home() / ".ledger" / "parse-cache.json")
    agg = Aggregator()
    # Force UTF-8 on Windows to handle sparkline block characters (▁▂▃▄▅▆▇)
    # that can't be encoded in cp1252 by the legacy Windows console renderer.
    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    console = Console(file=out)

    console.print("[dim]scanning transcript history…[/dim]")

    if args.once:
        _cold_scan(agg, cache, root)
        console.print(render_dashboard(build_state(agg, config, datetime.now(timezone.utc))))
        return 0

    # Live path: prime the watcher to current EOF FIRST, then cold-scan history.
    # Any line appended during the cold scan is re-read by the first poll (from the
    # primed offset) and absorbed by the aggregator's requestId dedup — no lost update.
    watcher = Watcher()
    watcher.prime(root)
    _cold_scan(agg, cache, root)

    notifier = Notifier(Path.home() / ".ledger" / "alerts.log")
    crossings = CrossingTracker()

    try:
        with Live(console=console, screen=True, auto_refresh=False) as live:
            while True:
                for event in watcher.poll(root):
                    agg.add(event)
                now = datetime.now(timezone.utc)
                state = build_state(agg, config, now)
                if config.notify:
                    notifier.emit(crossings.check(state.budget))
                live.update(render_dashboard(state), refresh=True)
                time.sleep(_TICK_SECONDS)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
