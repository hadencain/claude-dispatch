from datetime import datetime, timezone

from ledger.models import UsageEvent
from ledger.pricing import cost, usage_units


def _event(model="claude-opus-4-8", **kw) -> UsageEvent:
    base = dict(
        session_id="s", project="p", model=model,
        timestamp=datetime(2026, 6, 25, tzinfo=timezone.utc), request_id="r",
        input_tokens=0, output_tokens=0, cache_read_tokens=0,
        cache_write_5m_tokens=0, cache_write_1h_tokens=0,
        web_search_requests=0, web_fetch_requests=0,
    )
    base.update(kw)
    return UsageEvent(**base)


def test_usage_units_weighting_is_model_agnostic():
    # weights: in 1, out 5, cache_read 0.1, cache_write_5m 1.25, cache_write_1h 2.0
    e = dict(input_tokens=1000, output_tokens=1000, cache_read_tokens=1000,
             cache_write_5m_tokens=1000, cache_write_1h_tokens=1000)
    expected = 1000 * 1 + 1000 * 5 + 1000 * 0.1 + 1000 * 1.25 + 1000 * 2.0
    assert usage_units(_event(model="claude-opus-4-8", **e)) == expected
    # Unknown model gets the same units — no model lookup.
    assert usage_units(_event(model="claude-future-9", **e)) == expected


def test_usage_units_output_weighted_five_times_input():
    assert usage_units(_event(output_tokens=1000)) == 5 * usage_units(_event(input_tokens=1000))


def test_opus_input_output_and_cache_multipliers():
    # opus input 5/MTok, output 25/MTok
    c = cost(_event(input_tokens=1_000_000, output_tokens=1_000_000,
                    cache_read_tokens=1_000_000,
                    cache_write_5m_tokens=1_000_000,
                    cache_write_1h_tokens=1_000_000))
    assert c.input == 5.0
    assert c.output == 25.0
    assert c.cache_read == 0.5          # 0.1 x 5
    assert c.cache_write_5m == 6.25     # 1.25 x 5
    assert c.cache_write_1h == 10.0     # 2 x 5
    assert c.unpriced is False


def test_web_search_billed_per_thousand():
    c = cost(_event(web_search_requests=500), web_search_usd_per_1k=10.0)
    assert c.web == 5.0


def test_unknown_model_is_unpriced_with_zero_dollars():
    c = cost(_event(model="claude-future-9", input_tokens=1_000_000))
    assert c.unpriced is True
    assert c.total == 0.0
