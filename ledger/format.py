"""Pure display formatters shared by the live TUI and the dispatch-hub summary.

No third-party or sibling-module dependencies — safe to import anywhere without
pulling in rich, psutil, or the resources layer.
"""
from __future__ import annotations

_BLOCKS = " ▁▂▃▄▅▆▇█"


def units(v: float) -> str:
    """Compact weighted-usage figure, e.g. 14_000_000 -> '14M', 2_100_000 -> '2.1M'."""
    if v >= 1_000_000:
        s = f"{v / 1_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{s}M"
    if v >= 1_000:
        return f"{v / 1_000:.0f}K"
    return f"{v:.0f}"


def short_project(name: str) -> str:
    """Encoded transcript dir names look like
    'C--Users-haden-Documents-Ship-src-<proj>'. Show the readable tail after the
    workspace 'src' marker; otherwise fall back to the trailing chars."""
    marker = "-src-"
    i = name.rfind(marker)
    if i != -1:
        return name[i + len(marker):]
    return name[-24:]


def bar(frac: float, width: int = 12) -> str:
    filled = max(0, min(width, round(frac * width)))
    return "█" * filled + "░" * (width - filled)


def sparkline(values: list[float]) -> str:
    if not values:
        return ""
    hi = max(values)
    if hi <= 0:
        return _BLOCKS[0] * len(values)
    return "".join(_BLOCKS[int(v / hi * (len(_BLOCKS) - 1))] for v in values)
