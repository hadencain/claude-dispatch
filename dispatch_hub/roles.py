from __future__ import annotations

import json
from pathlib import Path

from .models import Role

DEFAULT_ROLES: list[Role] = [
    Role("Architect",
         "You are the Architect. Focus on system design, module boundaries, "
         "interfaces, and trade-offs. Propose structure and review designs; do not "
         "write implementation code unless explicitly asked. Push back on premature "
         "complexity and call out where boundaries are unclear.",
         builtin=True),
    Role("Backend",
         "You are the Backend engineer. Focus on data models, business logic, APIs, "
         "persistence, and their tests. Implement server-side and core logic. Defer UI "
         "and styling to the Frontend role and large-scale structure to the Architect.",
         builtin=True),
    Role("Frontend",
         "You are the Frontend engineer. Focus on UI, components, layout, state "
         "management, and user-facing behavior. Implement and refine the interface. "
         "Defer data-model and server-logic decisions to the Backend role.",
         builtin=True),
    Role("QA",
         "You are QA. Focus on testing, edge cases, regressions, and verification. "
         "Write and run tests, reproduce bugs, and report findings precisely with steps "
         "to reproduce. Do not implement features; verify them and surface gaps.",
         builtin=True),
]


class RoleStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def ensure_seeded(self) -> None:
        if not self.path.exists():
            self.save(DEFAULT_ROLES)

    def load(self) -> list[Role]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return [Role.from_dict(d) for d in data]

    def save(self, roles: list[Role]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([r.to_dict() for r in roles], indent=2), encoding="utf-8"
        )

    def get(self, name: str) -> Role | None:
        for r in self.load():
            if r.name == name:
                return r
        return None

    def charters(self) -> dict[str, str]:
        return {r.name: r.charter for r in self.load()}

    def upsert(self, role: Role) -> None:
        roles = self.load()
        for i, r in enumerate(roles):
            if r.name == role.name:
                roles[i] = role
                break
        else:
            roles.append(role)
        self.save(roles)

    def delete(self, name: str) -> None:
        self.save([r for r in self.load() if r.name != name])
