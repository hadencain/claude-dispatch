from datetime import datetime, timezone

from ledger.models import UsageEvent


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
