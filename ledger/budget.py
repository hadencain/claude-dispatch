from __future__ import annotations

from dataclasses import dataclass

OK = "ok"
WARN = "warn"
OVER = "over"


@dataclass
class BudgetReport:
    day_state: str
    session_states: dict[str, str]


def _state(value: float, budget: float, warn_ratio: float) -> str:
    if budget <= 0:
        return OK
    if value >= budget:
        return OVER
    if value >= budget * warn_ratio:
        return WARN
    return OK


def evaluate(day_total: float, session_costs: dict[str, float],
             daily_budget: float, per_session_budget: float,
             warn_ratio: float) -> BudgetReport:
    return BudgetReport(
        day_state=_state(day_total, daily_budget, warn_ratio),
        session_states={
            sid: _state(c, per_session_budget, warn_ratio)
            for sid, c in session_costs.items()
        },
    )


class CrossingTracker:
    def __init__(self) -> None:
        self._fired: set[str] = set()

    def check(self, report: BudgetReport) -> list[str]:
        new: list[str] = []
        keys = {"day": report.day_state}
        for sid, state in report.session_states.items():
            keys[f"session:{sid}"] = state
        for key, state in keys.items():
            if state == OVER and key not in self._fired:
                self._fired.add(key)
                new.append(key)
            elif state != OVER:
                self._fired.discard(key)  # reset so a later crossing fires again
        return new
