from __future__ import annotations

import json
import sys
from pathlib import Path

from .models import Profile


class ProfileStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def path_for(self, name: str) -> Path:
        return self.directory / f"{name}.json"

    def save(self, profile: Profile) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path_for(profile.name).write_text(
            json.dumps(profile.to_dict(), indent=2), encoding="utf-8"
        )

    def load(self, name: str) -> Profile:
        data = json.loads(self.path_for(name).read_text(encoding="utf-8"))
        return Profile.from_dict(data)

    def delete(self, name: str) -> None:
        self.path_for(name).unlink(missing_ok=True)

    def list(self) -> list[str]:
        if not self.directory.exists():
            return []
        names: list[str] = []
        for f in sorted(self.directory.glob("*.json")):
            try:
                json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                print(f"warning: skipping corrupt profile '{f.stem}'", file=sys.stderr)
                continue
            names.append(f.stem)
        return names
