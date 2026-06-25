import json

from ledger.watch import Watcher


def _line(request_id):
    return json.dumps({
        "type": "assistant", "sessionId": "s", "timestamp": "2026-06-25T00:00:00Z",
        "requestId": request_id, "message": {"model": "claude-opus-4-8",
        "usage": {"input_tokens": 1, "output_tokens": 1}}}) + "\n"


def test_poll_emits_only_appended_complete_lines(tmp_path):
    proj = tmp_path / "projdir"
    proj.mkdir()
    f = proj / "s.jsonl"
    f.write_text(_line("first"), encoding="utf-8")
    w = Watcher()
    assert [e.request_id for e in w.poll(tmp_path)] == ["first"]
    # append one complete line and one partial (no newline yet)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(_line("second"))
        fh.write('{"partial":')
    assert [e.request_id for e in w.poll(tmp_path)] == ["second"]
    # finish the partial line
    with f.open("a", encoding="utf-8") as fh:
        fh.write(' "x"}\n')  # not an assistant line -> yields nothing, no crash
    assert w.poll(tmp_path) == []


def test_prime_skips_existing_then_tails_new(tmp_path):
    proj = tmp_path / "projdir"
    proj.mkdir()
    f = proj / "s.jsonl"
    f.write_text(_line("old"), encoding="utf-8")
    w = Watcher()
    w.prime(tmp_path)
    assert w.poll(tmp_path) == []  # "old" already counted by prime
    with f.open("a", encoding="utf-8") as fh:
        fh.write(_line("new"))
    assert [e.request_id for e in w.poll(tmp_path)] == ["new"]


def test_truncation_resets_offset(tmp_path):
    proj = tmp_path / "projdir"
    proj.mkdir()
    f = proj / "s.jsonl"
    f.write_text(_line("a") + _line("b"), encoding="utf-8")
    w = Watcher()
    w.poll(tmp_path)
    f.write_text(_line("c"), encoding="utf-8")  # shorter than before
    assert [e.request_id for e in w.poll(tmp_path)] == ["c"]
