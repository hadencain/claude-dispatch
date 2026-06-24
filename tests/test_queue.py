from dispatch_hub.queue import QueuedItem, read_queued, move_to_in_progress

SAMPLE = (
    "## Queued\n"
    "\n"
    "- claude-dispatch  creating new repos\n"
    "- voice formant replicator/visualizer\n"
    "\n"
    "## In Progress\n"
    "\n"
    "- Senses: port senses-audio (started 2026-06-24)\n"
    "\n"
    "## Done\n"
    "\n"
    "- old finished thing\n"
)


def test_read_queued_returns_only_queued_bullets():
    items = read_queued(SAMPLE)
    assert [i.text for i in items] == [
        "claude-dispatch  creating new repos",
        "voice formant replicator/visualizer",
    ]
    # raw preserves the full original line for later exact-match moves
    assert items[0].raw == "- claude-dispatch  creating new repos"


def test_read_queued_ignores_in_progress_and_done():
    items = read_queued(SAMPLE)
    texts = [i.text for i in items]
    assert "old finished thing" not in texts
    assert all("Senses" not in t for t in texts)


def test_move_to_in_progress_relocates_and_dates_line():
    raw = "- voice formant replicator/visualizer"
    out = move_to_in_progress(SAMPLE, [raw], "2026-06-24")
    # gone from Queued
    assert "- voice formant replicator/visualizer\n" not in out.split("## In Progress")[0]
    # present and dated at top of In Progress
    in_progress = out.split("## In Progress")[1].split("## Done")[0]
    assert "- voice formant replicator/visualizer (dispatched 2026-06-24)" in in_progress


def test_move_to_in_progress_preserves_done_and_untouched_bullets():
    out = move_to_in_progress(SAMPLE, ["- voice formant replicator/visualizer"], "2026-06-24")
    # Done section byte-identical
    assert out.split("## Done")[1] == SAMPLE.split("## Done")[1]
    # the other queued bullet still under Queued, unchanged
    queued = out.split("## In Progress")[0]
    assert "- claude-dispatch  creating new repos\n" in queued


def test_move_to_in_progress_skips_unmatched_line():
    out = move_to_in_progress(SAMPLE, ["- not in the file"], "2026-06-24")
    assert out == SAMPLE  # nothing matched => nothing changed


def test_move_to_in_progress_preserves_crlf_line_endings():
    crlf = SAMPLE.replace("\n", "\r\n")
    out = move_to_in_progress(crlf, ["- voice formant replicator/visualizer"], "2026-06-24")
    # the rewrite keeps Windows line endings and introduces no bare \n
    assert "\r\n" in out
    assert "\n" not in out.replace("\r\n", "")
    assert "- voice formant replicator/visualizer (dispatched 2026-06-24)" in out


def test_move_to_in_progress_creates_header_when_in_progress_absent():
    text = "## Queued\n\n- lone task\n"
    out = move_to_in_progress(text, ["- lone task"], "2026-06-24")
    # a fresh In Progress header is appended with the dated, relocated line
    assert "## In Progress" in out
    in_progress = out.split("## In Progress")[1]
    assert "- lone task (dispatched 2026-06-24)" in in_progress
    # and it is gone from the Queued section
    assert "- lone task\n" not in out.split("## In Progress")[0]
