from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .models import UsageEvent

Parser = Callable[[Path, str], list[UsageEvent]]


class ParseCache:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._entries: dict[str, dict] = {}
        if self.path.exists():
            try:
                self._entries = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self._entries = {}

    def get_or_parse(self, file: Path, project: str, parser: Parser) -> list[UsageEvent]:
        file = Path(file)
        key = str(file)
        stat = file.stat()
        sig = [stat.st_size, stat.st_mtime_ns]
        entry = self._entries.get(key)
        if entry is not None and entry.get("sig") == sig:
            return [UsageEvent.from_dict(d) for d in entry["events"]]
        events = parser(file, project)
        self._entries[key] = {"sig": sig, "events": [e.to_dict() for e in events]}
        return events

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._entries), encoding="utf-8")
