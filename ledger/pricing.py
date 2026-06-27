from __future__ import annotations

from .models import UsageEvent

# Weighted "usage units" — a model-agnostic measure of real model load, with no
# dollars. Output is exactly 5x input for every Claude model (opus 25/5,
# sonnet 15/3, haiku 5/1), so the per-model rate factors out cleanly: a usage
# unit is just a weighted token. Cache reads (replays) count little; writes more.
_U_INPUT = 1.0
_U_OUTPUT = 5.0
_U_CACHE_READ = 0.1
_U_CACHE_WRITE_5M = 1.25
_U_CACHE_WRITE_1H = 2.0


def usage_units(event: UsageEvent) -> float:
    """Weighted token consumption for an event (no dollars, model-agnostic)."""
    return (
        event.input_tokens * _U_INPUT
        + event.output_tokens * _U_OUTPUT
        + event.cache_read_tokens * _U_CACHE_READ
        + event.cache_write_5m_tokens * _U_CACHE_WRITE_5M
        + event.cache_write_1h_tokens * _U_CACHE_WRITE_1H
    )
