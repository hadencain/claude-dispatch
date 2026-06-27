from datetime import datetime, timezone

from ledger.aggregate import ProjectRollup, SessionRollup, Totals
from ledger.budget import OK, BudgetReport
from ledger.resources import GpuSnapshot, ProcRow, SystemSnapshot
from ledger.tui import DashboardState, render_dashboard


def test_render_dashboard_returns_renderable_without_error():
    state = DashboardState(
        totals=Totals(all_time=10_000_000.0, today=2_000_000.0, this_week=5_000_000.0, active_count=1),
        sessions=[SessionRollup("s1", "proj", "claude-opus-4-8", 1000, 100, 50,
                                1500.0, datetime(2026, 6, 25, tzinfo=timezone.utc))],
        projects=[ProjectRollup("proj", 10_000_000.0, 2_000_000.0)],
        day_usage={"2026-06-25": 2_000_000.0},
        gpu=GpuSnapshot(0, 0, 4096, 41),
        system=SystemSnapshot(14.0, 9_000_000_000, 32_000_000_000),
        procs=[ProcRow("node", 1, 3.1, 412_000_000, 0)],
        budget=BudgetReport(day_state=OK, session_states={"s1": OK}),
        history_days=14,
    )
    group = render_dashboard(state)
    # Rendering to a string must not raise.
    from rich.console import Console
    import io
    Console(file=io.StringIO(), width=100).print(group)
