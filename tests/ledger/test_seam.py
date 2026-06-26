import json
from datetime import date, datetime, timezone

from ledger.aggregate import Aggregator
from ledger.transcripts import parse_file, project_label
from ledger.watch import Watcher

_TODAY = date(2026, 6, 25)
_NOW = datetime(2026, 6, 25, 0, 0, 0, tzinfo=timezone.utc)


def _line(request_id):
    return json.dumps({
        "type": "assistant", "sessionId": "s", "timestamp": "2026-06-25T00:00:00Z",
        "requestId": request_id, "message": {"model": "claude-opus-4-8",
        "usage": {"input_tokens": 1000, "output_tokens": 100}}}) + "\n"


def test_prime_then_coldscan_then_poll_equals_full_refold(tmp_path):
    root = tmp_path / "projects"
    proj = root / "projdir"
    proj.mkdir(parents=True)
    f = proj / "s.jsonl"
    f.write_text(_line("a") + _line("b"), encoding="utf-8")

    # Live-path ordering: prime first, then cold-scan, then an append lands in the
    # startup gap, then poll. The appended line must be counted exactly once.
    agg = Aggregator()
    watcher = Watcher()
    watcher.prime(root)
    for ev in parse_file(f, project_label(f)):
        agg.add(ev)
    with f.open("a", encoding="utf-8") as fh:   # appended during/after cold scan
        fh.write(_line("c"))
    for ev in watcher.poll(root):
        agg.add(ev)

    # Oracle: a single full re-fold of the final file state.
    full = Aggregator()
    for ev in parse_file(f, project_label(f)):
        full.add(ev)

    assert agg.totals(_TODAY, _NOW, 600).all_time == full.totals(_TODAY, _NOW, 600).all_time
    assert agg.totals(_TODAY, _NOW, 600).all_time > 0
