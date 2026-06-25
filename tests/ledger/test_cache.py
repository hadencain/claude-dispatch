from datetime import datetime, timezone

from ledger.cache import ParseCache
from ledger.models import UsageEvent


def _parser_returning(events, counter):
    def parse(_path, _project):
        counter.append(1)
        return events
    return parse


def _event():
    return UsageEvent(
        session_id="s", project="p", model="claude-opus-4-8",
        timestamp=datetime(2026, 6, 25, tzinfo=timezone.utc), request_id="r",
        input_tokens=1, output_tokens=1, cache_read_tokens=0,
        cache_write_5m_tokens=0, cache_write_1h_tokens=0,
        web_search_requests=0, web_fetch_requests=0,
    )


def test_unchanged_file_served_from_cache(tmp_path):
    f = tmp_path / "a.jsonl"
    f.write_text("x", encoding="utf-8")
    calls: list[int] = []
    cache = ParseCache(tmp_path / "cache.json")
    parser = _parser_returning([_event()], calls)
    first = cache.get_or_parse(f, "p", parser)
    second = cache.get_or_parse(f, "p", parser)
    assert first == second
    assert len(calls) == 1  # parsed once, second call cached


def test_changed_file_reparsed(tmp_path):
    f = tmp_path / "a.jsonl"
    f.write_text("x", encoding="utf-8")
    calls: list[int] = []
    cache = ParseCache(tmp_path / "cache.json")
    parser = _parser_returning([_event()], calls)
    cache.get_or_parse(f, "p", parser)
    f.write_text("xy", encoding="utf-8")  # size changes
    cache.get_or_parse(f, "p", parser)
    assert len(calls) == 2


def test_save_and_reload_persists_events(tmp_path):
    f = tmp_path / "a.jsonl"
    f.write_text("x", encoding="utf-8")
    cache_path = tmp_path / "cache.json"
    calls: list[int] = []
    parser = _parser_returning([_event()], calls)
    cache = ParseCache(cache_path)
    cache.get_or_parse(f, "p", parser)
    cache.save()

    reloaded = ParseCache(cache_path)
    result = reloaded.get_or_parse(f, "p", parser)
    assert result == [_event()]
    assert len(calls) == 1  # served from persisted cache, parser not called again
