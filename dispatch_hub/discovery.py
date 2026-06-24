"""Discover project directories under a workspace root.

Used by the create-session flow so the user can pick a project from a flat,
searchable list instead of pasting a path. A directory counts as a project if
it contains any marker file; noise dirs (venvs, build output, vcs internals)
are pruned so the walk stays fast and the list stays clean.
"""

from __future__ import annotations

import os
import stat as _stat
from pathlib import Path

# Windows file attributes that mean "touching this will prompt or hydrate":
# reparse points (junctions / symlinks) and cloud-only placeholders that
# trigger a download or access check when read. We never descend into these.
_REPARSE = getattr(_stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_OFFLINE = getattr(_stat, "FILE_ATTRIBUTE_OFFLINE", 0x1000)
_RECALL_ON_OPEN = 0x00040000
_RECALL_ON_DATA = 0x00400000
_AVOID_ATTRS = _REPARSE | _OFFLINE | _RECALL_ON_OPEN | _RECALL_ON_DATA

# A directory holding any of these is treated as a project root.
MARKERS = {
    ".git", "CLAUDE.md", "package.json", "requirements.txt", "pyproject.toml",
    "CMakeLists.txt", "Cargo.toml", "go.mod", "build.gradle", "config.lua",
}

# Never descend into these — they're large and never project roots.
EXCLUDE_DIRS = {
    ".git", "venv", ".venv", "env", "node_modules", "build", "dist", "out",
    "__pycache__", ".pytest_cache", "scratch", ".gradle", ".idea", ".vs",
    "target", "bin", "obj",
}


def default_workspace_root() -> Path:
    """The Ship workspace root, derived from this file's location.

    dispatch_hub/discovery.py -> parents: 0=dispatch_hub, 1=projectHub,
    2=src, 3=Ship.
    """
    return Path(__file__).resolve().parents[3]


def _avoid(entry: os.DirEntry) -> bool:
    """True for reparse/cloud entries we must not descend into (they would
    trigger a permission check or a cloud download). Stat without following the
    link so we inspect the placeholder itself, not its target."""
    try:
        attrs = entry.stat(follow_symlinks=False).st_file_attributes
    except (OSError, AttributeError):
        return False
    return bool(attrs & _AVOID_ATTRS)


def discover_projects(root: Path, max_depth: int = 4) -> list[Path]:
    """Return project directories under ``root``, sorted by display path.

    Descends at most ``max_depth`` levels below ``root``. A dir with a marker
    is recorded and still descended into (monorepos nest projects). Excluded
    dirs, dot-dirs, symlinks/junctions, and cloud-only placeholders are never
    entered, so the scan never follows a link into a protected location or
    forces a OneDrive download — both of which prompt for access on Windows.
    """
    root = Path(root)
    found: list[Path] = []
    if not root.is_dir():
        return found

    def walk(path: str, depth: int) -> None:
        try:
            with os.scandir(path) as it:
                entries = list(it)
        except (PermissionError, OSError):
            return
        if {e.name for e in entries} & MARKERS:
            found.append(Path(path))
        if depth >= max_depth:
            return
        for e in entries:
            if e.name in EXCLUDE_DIRS or e.name.startswith("."):
                continue
            try:
                if not e.is_dir(follow_symlinks=False):
                    continue
            except OSError:
                continue
            if _avoid(e):
                continue
            walk(e.path, depth + 1)

    walk(str(root), 0)
    return sorted(set(found), key=lambda p: str(p).lower())
