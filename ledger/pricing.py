from __future__ import annotations

from .models import CostBreakdown, UsageEvent

# model id -> (input $/MTok, output $/MTok)
RATES: dict[str, tuple[float, float]] = {
    "claude-fable-5": (10.0, 50.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-opus-4-5": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}

_CACHE_READ_MULT = 0.1
_CACHE_WRITE_5M_MULT = 1.25
_CACHE_WRITE_1H_MULT = 2.0
_PER_TOKEN = 1_000_000


def cost(event: UsageEvent, web_search_usd_per_1k: float = 10.0) -> CostBreakdown:
    rate = RATES.get(event.model)
    if rate is None:
        return CostBreakdown(unpriced=True)
    in_rate, out_rate = rate
    return CostBreakdown(
        input=event.input_tokens * in_rate / _PER_TOKEN,
        output=event.output_tokens * out_rate / _PER_TOKEN,
        cache_read=event.cache_read_tokens * (in_rate * _CACHE_READ_MULT) / _PER_TOKEN,
        cache_write_5m=event.cache_write_5m_tokens * (in_rate * _CACHE_WRITE_5M_MULT) / _PER_TOKEN,
        cache_write_1h=event.cache_write_1h_tokens * (in_rate * _CACHE_WRITE_1H_MULT) / _PER_TOKEN,
        web=event.web_search_requests * web_search_usd_per_1k / 1000,
    )
