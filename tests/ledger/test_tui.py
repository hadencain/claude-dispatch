import io
from datetime import datetime, timezone

from rich.console import Console

from ledger.aggregate import ProjectRollup, SessionRollup, Totals
from ledger.budget import OK, BudgetReport
from ledger.resources import GpuSnapshot, ProcRow, SystemSnapshot
from ledger.tui import DashboardState, render_dashboard


def _state(show_resources: bool = True) -> DashboardState:
    return DashboardState(
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
        show_resources=show_resources,
    )


def _render(group) -> str:
    buf = io.StringIO()
    Console(file=buf, width=100).print(group)
    return buf.getvalue()


def test_render_dashboard_returns_renderable_without_error():
    text = _render(render_dashboard(_state(show_resources=True)))
    assert "Resources" in text


def test_render_hides_resources_when_gated_off():
    text = _render(render_dashboard(_state(show_resources=False)))
    assert "Resources" not in text
    assert "resources hidden" in text
