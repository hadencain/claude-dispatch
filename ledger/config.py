from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


@dataclass
class Config:
    # Usage-unit budgets (weighted tokens). 0 = disabled — set a ceiling to get
    # warn/over alerts. There's no sane default unit threshold, so off by default.
    daily_usage_budget: float = 0.0
    per_session_usage_budget: float = 0.0
    warn_ratio: float = 0.8
    notify: bool = True
    ai_process_names: list[str] = field(
        default_factory=lambda: ["node", "claude", "python", "ollama"])
    history_days: int = 14
    active_window_seconds: int = 600


def default_config_path() -> Path:
    return Path.home() / ".ledger" / "config.json"


def load(path: Path) -> Config:
    path = Path(path)
    if not path.exists():
        cfg = Config()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
        return cfg
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    known = {f.name for f in fields(Config)}
    return Config(**{k: v for k, v in data.items() if k in known})
