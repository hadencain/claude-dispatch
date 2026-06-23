from __future__ import annotations

import json
from pathlib import Path

from .models import Role


def roles_from_json(text: str) -> list[Role]:
    """Parse a JSON role definition (single object or array) into Roles.

    Accepts the shape produced by the role-authoring prompt:
    `[{"name": ..., "charter": ..., "builtin": false}, ...]`. Imported roles
    are always treated as custom (builtin=False) so the built-in protection
    stays meaningful — you don't import built-ins. Raises ValueError on any
    structurally invalid entry."""
    data = json.loads(text)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("expected a JSON object or array of role objects")
    roles: list[Role] = []
    for d in data:
        if not isinstance(d, dict) or "name" not in d or "charter" not in d:
            raise ValueError("each role needs a 'name' and a 'charter'")
        name = str(d["name"]).strip()
        charter = str(d["charter"]).strip()
        if not name or not charter:
            raise ValueError("'name' and 'charter' must be non-empty")
        roles.append(Role(name=name, charter=charter, builtin=False))
    return roles

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

    def import_roles(self, roles: list[Role]) -> tuple[int, int]:
        """Bulk add/replace roles by name in a single load+save.
        Returns (added, updated) counts."""
        current = self.load()
        index = {r.name: i for i, r in enumerate(current)}
        added = updated = 0
        for r in roles:
            if r.name in index:
                current[index[r.name]] = r
                updated += 1
            else:
                index[r.name] = len(current)
                current.append(r)
                added += 1
        self.save(current)
        return added, updated
