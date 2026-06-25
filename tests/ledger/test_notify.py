from ledger.notify import Notifier, format_alert


def test_format_alert_labels():
    assert format_alert("day") == "Daily budget exceeded"
    assert format_alert("session:abc") == "Session abc over budget"


def test_emit_writes_log_and_calls_toaster(tmp_path):
    log = tmp_path / "alerts.log"
    seen = []
    n = Notifier(log, toaster=lambda title, msg: seen.append((title, msg)))
    n.emit(["day", "session:abc"])
    text = log.read_text(encoding="utf-8")
    assert "Daily budget exceeded" in text
    assert "Session abc over budget" in text
    assert len(seen) == 2


def test_emit_swallows_toaster_errors(tmp_path):
    log = tmp_path / "alerts.log"
    def boom(_t, _m):
        raise RuntimeError("toast backend missing")
    n = Notifier(log, toaster=boom)
    n.emit(["day"])  # must not raise
    assert "Daily budget exceeded" in log.read_text(encoding="utf-8")
