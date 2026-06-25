from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .models import UsageEvent


def default_projects_root() -> Path:
    return Path.home() / ".claude" / "projects"


def project_label(path: Path) -> str:
    return path.parent.name


def iter_transcript_files(root: Path) -> Iterator[Path]:
    if not root.is_dir():
        return
    for project_dir in sorted(root.iterdir()):
        if not project_dir.is_dir():
            continue
        yield from sorted(project_dir.glob("*.jsonl"))


def _parse_ts(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def parse_line(raw: str, project: str, fallback_session: str) -> UsageEvent | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if obj.get("type") != "assistant":
        return None
    message = obj.get("message") or {}
    usage = message.get("usage")
    if not usage:
        return None

    creation = usage.get("cache_creation") or {}
    if creation:
        w5 = int(creation.get("ephemeral_5m_input_tokens", 0))
        w1 = int(creation.get("ephemeral_1h_input_tokens", 0))
    else:
        w5 = int(usage.get("cache_creation_input_tokens", 0))
        w1 = 0

    server = usage.get("server_tool_use") or {}
    try:
        ts = _parse_ts(obj["timestamp"])
    except (KeyError, ValueError):
        return None

    return UsageEvent(
        session_id=obj.get("sessionId") or fallback_session,
        project=project,
        model=message.get("model", "unknown"),
        timestamp=ts,
        request_id=obj.get("requestId", ""),
        input_tokens=int(usage.get("input_tokens", 0)),
        output_tokens=int(usage.get("output_tokens", 0)),
        cache_read_tokens=int(usage.get("cache_read_input_tokens", 0)),
        cache_write_5m_tokens=w5,
        cache_write_1h_tokens=w1,
        web_search_requests=int(server.get("web_search_requests", 0)),
        web_fetch_requests=int(server.get("web_fetch_requests", 0)),
    )


def parse_file(path: Path, project: str) -> list[UsageEvent]:
    fallback = path.stem
    events: list[UsageEvent] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return events
    for line in text.splitlines():
        event = parse_line(line, project, fallback)
        if event is not None:
            events.append(event)
    return events
