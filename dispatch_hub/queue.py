from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueuedItem:
    raw: str
    text: str


def _section_of(line: str, current: str | None) -> str | None:
    """Return the section name a header line opens, else the unchanged current."""
    s = line.strip()
    if s.startswith("## "):
        return s[3:].strip().lower()
    return current


def read_queued(text: str) -> list[QueuedItem]:
    items: list[QueuedItem] = []
    current: str | None = None
    for line in text.splitlines():
        current = _section_of(line, current)
        if line.strip().startswith("## "):
            continue
        if current == "queued" and line.lstrip().startswith("- "):
            bullet = line.strip()[2:].strip()
            items.append(QueuedItem(raw=line, text=bullet))
    return items


def move_to_in_progress(text: str, raw_lines: list[str], today: str) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    targets = set(raw_lines)
    lines = text.splitlines()

    moved: list[str] = []
    kept: list[str] = []
    current: str | None = None
    for line in lines:
        current = _section_of(line, current)
        if current == "queued" and not line.strip().startswith("## ") and line in targets:
            moved.append(f"{line} (dispatched {today})")
            continue
        kept.append(line)

    if not moved:
        return text  # nothing matched; do not rewrite, preserve bytes exactly

    out: list[str] = []
    inserted = False
    for line in kept:
        out.append(line)
        if not inserted and line.strip().lower() == "## in progress":
            out.extend(moved)
            inserted = True
    if not inserted:  # no In Progress header present; create one at the end
        out += ["", "## In Progress", *moved]

    result = newline.join(out)
    if text.endswith("\n"):
        result += newline
    return result
