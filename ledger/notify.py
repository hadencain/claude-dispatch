from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

Toaster = Callable[[str, str], None]


def format_alert(key: str) -> str:
    if key == "day":
        return "Daily budget exceeded"
    if key.startswith("session:"):
        return f"Session {key.split(':', 1)[1]} over budget"
    return f"Budget exceeded: {key}"


def _windows_toast(title: str, message: str) -> None:
    # Best-effort balloon via PowerShell; any failure is swallowed by the caller.
    script = (
        "[reflection.assembly]::LoadWithPartialName('System.Windows.Forms') > $null; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; "
        "$n.Visible = $true; "
        f"$n.ShowBalloonTip(5000, '{title}', '{message}', 'Warning')"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", script],
                   capture_output=True, timeout=5)


class Notifier:
    def __init__(self, log_path: Path, toaster: Toaster | None = None) -> None:
        self.log_path = Path(log_path)
        self.toaster = toaster if toaster is not None else _windows_toast

    def emit(self, new_over_keys: list[str]) -> None:
        if not new_over_keys:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).isoformat()
        with self.log_path.open("a", encoding="utf-8") as fh:
            for key in new_over_keys:
                label = format_alert(key)
                fh.write(f"{stamp}\t{label}\n")
                try:
                    self.toaster("Ledger", label)
                except Exception:
                    pass
