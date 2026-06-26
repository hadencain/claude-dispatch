from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .aggregate import ProjectRollup, SessionRollup, Totals
from .budget import OK, OVER, WARN, BudgetReport
from .resources import GpuSnapshot, ProcRow, SystemSnapshot

_BLOCKS = " ▁▂▃▄▅▆▇█"
_STATE_COLOR = {OK: "green", WARN: "yellow", OVER: "red"}


@dataclass
class DashboardState:
    totals: Totals
    sessions: list[SessionRollup]
    projects: list[ProjectRollup]
    day_costs: dict[str, float]
    gpu: GpuSnapshot | None
    system: SystemSnapshot
    procs: list[ProcRow]
    budget: BudgetReport
    unpriced: set[str]
    history_days: int


def sparkline(values: list[float]) -> str:
    if not values:
        return ""
    hi = max(values)
    if hi <= 0:
        return _BLOCKS[0] * len(values)
    out = []
    for v in values:
        idx = int(v / hi * (len(_BLOCKS) - 1))
        out.append(_BLOCKS[idx])
    return "".join(out)


def _money(v: float) -> str:
    return f"${v:,.2f}"


def _age(ts: datetime, now: datetime) -> str:
    secs = int((now - ts).total_seconds())
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m"
    return f"{secs // 3600}h"


def _header(t: Totals) -> Text:
    return Text(
        f"ledger    all-time {_money(t.all_time)}   today {_money(t.today)}   "
        f"this-month {_money(t.this_month)}   active {t.active_count}",
        style="bold",
    )


def _sessions_panel(state: DashboardState, now: datetime) -> Panel:
    table = Table(expand=True)
    for col in ("session", "project", "model", "in", "out", "cache", "$", "state", "age"):
        table.add_column(col)
    for s in state.sessions[:12]:
        state_str = state.budget.session_states.get(s.session_id, OK)
        table.add_row(
            s.session_id[:6], s.project[-24:], s.model.replace("claude-", ""),
            f"{s.input_tokens:,}", f"{s.output_tokens:,}", f"{s.cache_tokens:,}",
            _money(s.cost),
            Text(state_str, style=_STATE_COLOR.get(state_str, "white")),
            _age(s.last_activity, now),
        )
    return Panel(table, title="Active sessions")


def _projects_panel(state: DashboardState) -> Panel:
    table = Table(expand=True)
    table.add_column("project")
    table.add_column("all-time")
    table.add_column("today")
    for p in state.projects[:8]:
        table.add_row(p.project[-28:], _money(p.all_time), _money(p.today))
    return Panel(table, title="Projects")


def _history_panel(state: DashboardState) -> Panel:
    days = sorted(state.day_costs)[-state.history_days:]
    values = [state.day_costs[d] for d in days]
    today = _money(values[-1]) if values else "$0.00"
    body = Text(f"{sparkline(values)}   {today} today")
    return Panel(body, title=f"Last {state.history_days} days")


def _resources_panel(state: DashboardState) -> Panel:
    if state.gpu is not None:
        g = state.gpu
        gpu_line = f"GPU {g.util}%  VRAM {g.vram_used}/{g.vram_total}M  {g.temp}°C"
    else:
        gpu_line = "no NVIDIA GPU"
    sys = state.system
    head = Text(
        f"CPU {sys.cpu_percent:.0f}%  "
        f"RAM {sys.ram_used // 1_000_000_000}/{sys.ram_total // 1_000_000_000}G  {gpu_line}"
    )
    table = Table(expand=True)
    for col in ("name", "pid", "cpu", "ram(M)", "vram(M)", "project"):
        table.add_column(col)
    for p in state.procs[:10]:
        table.add_row(p.name, str(p.pid), f"{p.cpu:.0f}%",
                      str(p.ram // 1_000_000), str(p.vram), p.project or "—")
    return Panel(Group(head, table), title="Resources")


def _footer(state: DashboardState) -> Text:
    day = state.budget.day_state
    msg = Text(f"budget: today {day}", style=_STATE_COLOR.get(day, "white"))
    if state.unpriced:
        msg.append(f"   ·   {len(state.unpriced)} unpriced model(s)", style="yellow")
    msg.append("   ·   q quit", style="dim")
    return msg


def render_dashboard(state: DashboardState) -> Group:
    now = datetime.now(timezone.utc)
    return Group(
        _header(state.totals),
        _sessions_panel(state, now),
        _projects_panel(state),
        _history_panel(state),
        _resources_panel(state),
        _footer(state),
    )
