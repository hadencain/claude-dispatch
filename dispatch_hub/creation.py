"""Create new project directories under the workspace.

Pure derivation/validation plus one I/O function (``create_directory``). Shared
by the manual create flow and the AI queue-dispatch flow so both decide where a
new project lives the same way. Imports stdlib only — no TUI, no discovery.
"""

from __future__ import annotations

import re
from pathlib import Path

# Windows-illegal filename chars plus control chars. Each becomes a space, then
# runs of whitespace collapse to a single dash below.
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_dirname(name: str) -> str:
    """A safe single-segment directory name, casing preserved.

    Illegal characters become spaces, whitespace runs collapse to one dash, and
    leading/trailing dashes and dots are trimmed. Returns "" when nothing usable
    remains (e.g. all-whitespace or all-dots input).
    """
    cleaned = _ILLEGAL.sub(" ", name)
    cleaned = re.sub(r"\s+", "-", cleaned.strip())
    return cleaned.strip("-.")


def candidate_parents(root: Path, projects: list[Path]) -> list[Path]:
    """Parent folders a new project could live under, derived from discovered
    projects: ``root`` plus the parent of every project at or under ``root``.
    Deduped and sorted by display path. No hardcoded category list — the buckets
    track the workspace as it changes.
    """
    root = Path(root)
    out = {root}
    for p in projects:
        parent = Path(p).parent
        try:
            parent.relative_to(root)
        except ValueError:
            continue  # parent is outside the workspace; not an offerable bucket
        out.add(parent)
    return sorted(out, key=lambda p: str(p).lower())


def target_path(parent: Path, name: str) -> Path:
    """The directory that would be created for ``name`` under ``parent``."""
    return Path(parent) / sanitize_dirname(name)


def validate_new_dir(parent: Path, name: str, root: Path) -> str | None:
    """Return an error string if the new dir is invalid, else None."""
    parent, root = Path(parent), Path(root)
    if not sanitize_dirname(name):
        return "Name is empty after removing illegal characters."
    try:
        parent.relative_to(root)
    except ValueError:
        return "Parent folder must be inside the workspace."
    target = target_path(parent, name)
    if target.exists():
        return f"{target} already exists."
    return None


def create_directory(path: Path) -> None:
    """Create ``path`` (and any missing parents). Raises FileExistsError if it
    already exists — callers validate first; this is the backstop."""
    Path(path).mkdir(parents=True, exist_ok=False)
