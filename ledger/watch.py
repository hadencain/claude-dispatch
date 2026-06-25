from __future__ import annotations

from pathlib import Path

from .models import UsageEvent
from .transcripts import iter_transcript_files, parse_line, project_label


class Watcher:
    def __init__(self) -> None:
        self._offsets: dict[str, int] = {}

    def _read_new(self, file: Path, emit: bool) -> list[UsageEvent]:
        key = str(file)
        try:
            size = file.stat().st_size
        except OSError:
            return []
        offset = self._offsets.get(key, 0)
        if size < offset:          # truncated / rotated
            offset = 0
        if size == offset:
            self._offsets[key] = offset
            return []
        with file.open("rb") as fh:
            fh.seek(offset)
            chunk = fh.read(size - offset)
        nl = chunk.rfind(b"\n")
        if nl == -1:               # no complete line yet — hold
            return []
        complete = chunk[: nl + 1]
        self._offsets[key] = offset + len(complete)
        if not emit:
            return []
        project = project_label(file)
        fallback = file.stem
        events: list[UsageEvent] = []
        for line in complete.decode("utf-8", "replace").splitlines():
            event = parse_line(line, project, fallback)
            if event is not None:
                events.append(event)
        return events

    def prime(self, root: Path) -> None:
        for file in iter_transcript_files(root):
            self._read_new(file, emit=False)

    def poll(self, root: Path) -> list[UsageEvent]:
        events: list[UsageEvent] = []
        for file in iter_transcript_files(root):
            events.extend(self._read_new(file, emit=True))
        return events
