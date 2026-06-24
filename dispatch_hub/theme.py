"""Shared visual theme: light-grey accent for prompts + the startup splash."""

from __future__ import annotations

from questionary import Style
from rich.console import Console

# Light grey, readable on a dark terminal. Used as the single accent colour
# across every interactive prompt and the splash banner.
ACCENT = "#cfcfcf"
DIM = "#8a8a8a"

# Prompt marker shown before every question (replaces questionary's default "?").
MARK = "»"

# questionary style — every prompt routes through this so the accent is uniform.
STYLE = Style(
    [
        ("qmark", f"fg:{ACCENT} bold"),
        ("question", "bold"),
        ("answer", f"fg:{ACCENT} bold"),
        ("pointer", f"fg:{ACCENT} bold"),
        ("highlighted", f"fg:{ACCENT} bold"),
        ("selected", f"fg:{ACCENT}"),
        ("separator", f"fg:{DIM}"),
        ("instruction", f"fg:{DIM}"),
        ("text", ""),
        ("disabled", "fg:#5c5c5c italic"),
    ]
)

BANNER = """
▓█████  ██ ███▓███ ███▒██   █████  ▒█▒████  ██████ █▓   ██
█▒   █▒ ██ ██      ██   ██ ██   ▒█    █▓   ██      ██   █▓
██   ██ ██ ███████ ████▓█  ██▓████    ▓█   ██      ███▒██▓
██   ██ █▓      ██ ██      ██   ▒▒    █▓   ██      ██   █▒
█████▓  ██ ▒▓▒████ ██      ██   ▒▒    ██    ██████ ▓█   ██
"""


def print_splash(console: Console) -> None:
    """Print the startup banner in the light-grey accent."""
    console.print(f"[{ACCENT}]{BANNER}[/]")
    console.print(
        f"   [bold {ACCENT}]Claude Dispatch Hub[/]"
        f"   [{DIM}]- multi-agent Claude Code session launcher[/]\n"
    )
