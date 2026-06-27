import io
import json
from datetime import datetime, timezone

from rich.console import Console

from ledger.summary import usage_panel


def _line(request_id="r", project_session="s"):
    return json.dumps({
        "type": "assistant", "sessionId": project_session,
        "timestamp": "2026-06-25T00:00:00Z", "requestId": request_id,
        "message": {"model": "claude-opus-4-8",
                    "usage": {"input_tokens": 1000, "output_tokens": 200}}}) + "\n"


def _render(panel) -> str:
    buf = io.StringIO()
    Console(file=buf, width=80).print(panel)
    return buf.getvalue()


def test_usage_panel_reflects_data(tmp_path):
    root = tmp_path / "projects"
    proj = root / "C--Users-haden-Documents-Ship-src-demo"
    proj.mkdir(parents=True)
    (proj / "s.jsonl").write_text(_line(), encoding="utf-8")

    panel = usage_panel(
        root=root, cache_path=tmp_path / "cache.json",
        now=datetime(2026, 6, 25, 1, tzinfo=timezone.utc),
    )
    text = _render(panel)
    assert "Ledger" in text
    assert "demo" in text          # short_project name shown
    assert "units" in text


def test_usage_panel_empty_root_is_quiet(tmp_path):
    panel = usage_panel(root=tmp_path / "nonexistent", cache_path=tmp_path / "cache.json")
    text = _render(panel)
    assert "No Claude usage data yet" in text


def test_usage_panel_never_raises_on_bad_root(tmp_path):
    # A file where a directory is expected must not blow up the host tool.
    bad = tmp_path / "afile"
    bad.write_text("not a dir", encoding="utf-8")
    panel = usage_panel(root=bad, cache_path=tmp_path / "cache.json")
    assert _render(panel)  # renders something, no exception
