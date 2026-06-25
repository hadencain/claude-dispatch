from datetime import datetime, timezone

from ledger.models import CostBreakdown, UsageEvent


def _event() -> UsageEvent:
    return UsageEvent(
        session_id="s1", project="proj", model="claude-opus-4-8",
        timestamp=datetime(2026, 6, 25, 0, 51, 43, tzinfo=timezone.utc),
        request_id="req_1", input_tokens=100, output_tokens=10,
        cache_read_tokens=20, cache_write_5m_tokens=0, cache_write_1h_tokens=5,
        web_search_requests=0, web_fetch_requests=0,
    )


def test_usage_event_roundtrips_through_dict():
    e = _event()
    assert UsageEvent.from_dict(e.to_dict()) == e


def test_cost_breakdown_total_sums_dollar_fields():
    c = CostBreakdown(input=1.0, output=2.0, cache_read=0.5,
                      cache_write_5m=0.25, cache_write_1h=0.25, web=1.0)
    assert c.total == 5.0
    assert c.unpriced is False
