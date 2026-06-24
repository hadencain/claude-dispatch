from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Role:
    name: str
    charter: str

    def to_dict(self) -> dict:
        return {"name": self.name, "charter": self.charter}

    @classmethod
    def from_dict(cls, d: dict) -> "Role":
        return cls(name=d["name"], charter=d["charter"])


@dataclass
class Pane:
    directory: str
    role: str | None = None
    startup_prompt: str = ""
    title: str | None = None

    def to_dict(self) -> dict:
        return {
            "directory": self.directory,
            "role": self.role,
            "startup_prompt": self.startup_prompt,
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Pane":
        return cls(
            directory=d["directory"],
            role=d.get("role"),
            startup_prompt=d.get("startup_prompt", ""),
            title=d.get("title"),
        )


@dataclass
class Profile:
    name: str
    layout: str
    panes: list[Pane] = field(default_factory=list)
    created: str = ""
    modified: str = ""

    @classmethod
    def new(cls, name: str, layout: str, panes: list[Pane]) -> "Profile":
        ts = _now()
        return cls(name=name, layout=layout, panes=list(panes), created=ts, modified=ts)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "layout": self.layout,
            "panes": [p.to_dict() for p in self.panes],
            "created": self.created,
            "modified": self.modified,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        return cls(
            name=d["name"],
            layout=d["layout"],
            panes=[Pane.from_dict(p) for p in d.get("panes", [])],
            created=d.get("created", ""),
            modified=d.get("modified", ""),
        )
