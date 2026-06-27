from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .models import UsageEvent
from .pricing import usage_units


@dataclass
class SessionRollup:
    session_id: str
    project: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_tokens: int
    usage: float
    last_activity: datetime


@dataclass
class ProjectRollup:
    project: str
    all_time: float
    today: float


@dataclass
class Totals:
    all_time: float
    today: float
    this_week: float
    active_count: int


@dataclass
class _SessionAcc:
    session_id: str
    project: str
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_tokens: int = 0
    usage: float = 0.0
    last_activity: datetime | None = None


class Aggregator:
    def __init__(self) -> None:
        self._seen: set[str] = set()
        self._sessions: dict[str, _SessionAcc] = {}
        self._session_usage: dict[str, float] = {}
        self._project_usage: dict[str, float] = {}
        self._day_usage: dict[str, float] = {}
        self._project_day: dict[tuple[str, str], float] = {}

    def add(self, event: UsageEvent) -> bool:
        if event.request_id and event.request_id in self._seen:
            return False
        if event.request_id:
            self._seen.add(event.request_id)

        u = usage_units(event)

        acc = self._sessions.get(event.session_id)
        if acc is None:
            acc = _SessionAcc(event.session_id, event.project)
            self._sessions[event.session_id] = acc
        acc.model = event.model
        acc.input_tokens += event.input_tokens
        acc.output_tokens += event.output_tokens
        acc.cache_tokens += (event.cache_read_tokens
                             + event.cache_write_5m_tokens
                             + event.cache_write_1h_tokens)
        acc.usage += u
        if acc.last_activity is None or event.timestamp > acc.last_activity:
            acc.last_activity = event.timestamp

        self._session_usage[event.session_id] = self._session_usage.get(event.session_id, 0.0) + u
        self._project_usage[event.project] = self._project_usage.get(event.project, 0.0) + u
        day = event.timestamp.date().isoformat()
        self._day_usage[day] = self._day_usage.get(day, 0.0) + u
        key = (event.project, day)
        self._project_day[key] = self._project_day.get(key, 0.0) + u
        return True

    def sessions(self) -> list[SessionRollup]:
        out = [
            SessionRollup(a.session_id, a.project, a.model, a.input_tokens,
                          a.output_tokens, a.cache_tokens, a.usage, a.last_activity)
            for a in self._sessions.values() if a.last_activity is not None
        ]
        out.sort(key=lambda s: s.last_activity, reverse=True)
        return out

    def active_sessions(self, now: datetime, window_seconds: int) -> list[SessionRollup]:
        cutoff = now - timedelta(seconds=window_seconds)
        return [s for s in self.sessions() if s.last_activity >= cutoff]

    def session_usage(self) -> dict[str, float]:
        return dict(self._session_usage)

    def projects(self, today: date) -> list[ProjectRollup]:
        today_iso = today.isoformat()
        out = [
            ProjectRollup(project, total, self._project_day.get((project, today_iso), 0.0))
            for project, total in self._project_usage.items()
        ]
        out.sort(key=lambda p: p.all_time, reverse=True)
        return out

    def day_usage(self) -> dict[str, float]:
        return dict(self._day_usage)

    def totals(self, today: date, now: datetime, window_seconds: int) -> Totals:
        all_time = sum(self._day_usage.values())
        today_iso = today.isoformat()
        this_iso_week = today.isocalendar()[:2]  # (ISO year, ISO week)
        this_week = sum(
            v for d, v in self._day_usage.items()
            if date.fromisoformat(d).isocalendar()[:2] == this_iso_week
        )
        return Totals(
            all_time=all_time,
            today=self._day_usage.get(today_iso, 0.0),
            this_week=this_week,
            active_count=len(self.active_sessions(now, window_seconds)),
        )
