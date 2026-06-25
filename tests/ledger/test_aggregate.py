from datetime import date, datetime, timezone

from ledger.aggregate import Aggregator
from ledger.models import UsageEvent


def _event(request_id="r1", session="s1", model="claude-opus-4-8",
           when=datetime(2026, 6, 25, 12, tzinfo=timezone.utc), inp=1_000_000):
    return UsageEvent(
        session_id=session, project="proj", model=model, timestamp=when,
        request_id=request_id, input_tokens=inp, output_tokens=0,
        cache_read_tokens=0, cache_write_5m_tokens=0, cache_write_1h_tokens=0,
        web_search_requests=0, web_fetch_requests=0,
    )


def test_duplicate_request_id_counted_once():
    agg = Aggregator()
    assert agg.add(_event(request_id="dup")) is True
    assert agg.add(_event(request_id="dup")) is False
    assert agg.totals(date(2026, 6, 25), datetime(2026, 6, 25, 12, tzinfo=timezone.utc), 600).all_time == 5.0


def test_empty_request_id_not_deduped():
    agg = Aggregator()
    assert agg.add(_event(request_id="")) is True
    assert agg.add(_event(request_id="")) is True


def test_active_sessions_within_window():
    now = datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc)
    agg = Aggregator()
    agg.add(_event(request_id="a", session="recent", when=now))
    agg.add(_event(request_id="b", session="stale",
                   when=datetime(2026, 6, 25, 11, 0, 0, tzinfo=timezone.utc)))
    active = agg.active_sessions(now, window_seconds=600)
    assert [s.session_id for s in active] == ["recent"]


def test_unpriced_model_tracked_and_excluded_from_dollars():
    agg = Aggregator()
    agg.add(_event(request_id="u", model="claude-future-9"))
    assert agg.unpriced_models() == {"claude-future-9"}
    assert agg.totals(date(2026, 6, 25), datetime(2026, 6, 25, 12, tzinfo=timezone.utc), 600).all_time == 0.0
