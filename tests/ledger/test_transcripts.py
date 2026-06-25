import json

from ledger.transcripts import parse_file, parse_line, project_label


def _assistant_line(request_id="req_1", model="claude-opus-4-8"):
    return json.dumps({
        "type": "assistant", "sessionId": "sess-uuid",
        "timestamp": "2026-06-25T00:51:43.924Z", "requestId": request_id,
        "message": {"model": model, "usage": {
            "input_tokens": 100, "cache_read_input_tokens": 50,
            "cache_creation_input_tokens": 30, "output_tokens": 8,
            "cache_creation": {"ephemeral_5m_input_tokens": 10,
                               "ephemeral_1h_input_tokens": 20},
            "server_tool_use": {"web_search_requests": 1, "web_fetch_requests": 0},
        }},
    })


def test_parse_line_extracts_split_cache_tokens():
    e = parse_line(_assistant_line(), "proj", "fallback")
    assert e is not None
    assert e.input_tokens == 100
    assert e.cache_read_tokens == 50
    assert e.cache_write_5m_tokens == 10
    assert e.cache_write_1h_tokens == 20
    assert e.web_search_requests == 1
    assert e.timestamp.tzinfo is not None


def test_parse_line_falls_back_to_lump_cache_when_no_split():
    raw = json.dumps({
        "type": "assistant", "sessionId": "s", "timestamp": "2026-06-25T00:00:00Z",
        "requestId": "r", "message": {"model": "claude-opus-4-8", "usage": {
            "input_tokens": 1, "cache_creation_input_tokens": 40, "output_tokens": 1}},
    })
    e = parse_line(raw, "proj", "fb")
    assert e.cache_write_5m_tokens == 40
    assert e.cache_write_1h_tokens == 0


def test_parse_line_skips_non_assistant_and_malformed():
    assert parse_line('{"type": "user"}', "p", "fb") is None
    assert parse_line("not json", "p", "fb") is None
    assert parse_line('{"type": "assistant", "message": {}}', "p", "fb") is None


def test_parse_file_uses_filename_as_fallback_session(tmp_path):
    f = tmp_path / "the-session-id.jsonl"
    line = json.loads(_assistant_line())
    del line["sessionId"]
    f.write_text(json.dumps(line) + "\n", encoding="utf-8")
    events = parse_file(f, "proj")
    assert len(events) == 1
    assert events[0].session_id == "the-session-id"


def test_project_label_is_parent_dir_name(tmp_path):
    d = tmp_path / "C--Users-haden-proj"
    d.mkdir()
    f = d / "x.jsonl"
    f.write_text("", encoding="utf-8")
    assert project_label(f) == "C--Users-haden-proj"
