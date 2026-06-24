from __future__ import annotations

import json
from dataclasses import dataclass

DEFAULT_MODEL = "claude-sonnet-4-6"
NONE_ROLE = "(none)"

SYSTEM_PROMPT = (
    "You assign software work items to a role, a project directory, and a concrete "
    "startup prompt for a coding agent. You are given a list of items (each with an "
    "index), a list of allowed role names, and a list of allowed project directories. "
    "For every item return one object. 'role' MUST be exactly one of the allowed role "
    "names, or the string '(none)' if none fit. 'directory' MUST be exactly one of the "
    "allowed directories. 'startup_prompt' is a clear first instruction for the agent, "
    "expanded from the terse item into something actionable. 'reason' is one short "
    "phrase. Respond with ONLY a JSON array of objects with keys: item_index, role, "
    "directory, startup_prompt, reason. No prose, no markdown fences."
)


@dataclass
class Proposal:
    item_index: int
    item_text: str
    role: str | None
    directory: str
    startup_prompt: str
    reason: str
    unresolved: bool


def build_user_payload(items: list[str], role_names: list[str], directories: list[str]) -> str:
    return json.dumps({
        "items": [{"index": i, "text": t} for i, t in enumerate(items)],
        "allowed_roles": role_names,
        "allowed_directories": directories,
    }, indent=2)


def _strip_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s[: s.rfind("```")]
    return s.strip()


def parse_response(text: str, items: list[str], role_names: list[str],
                   directories: list[str]) -> list[Proposal]:
    data = json.loads(_strip_fences(text))
    dir_set = set(directories)
    role_set = set(role_names)
    props: list[Proposal] = []
    for obj in data:
        idx = int(obj["item_index"])
        item_text = items[idx]
        raw_role = obj.get("role")
        role = raw_role if raw_role in role_set else None
        directory = obj.get("directory", "")
        prompt = (obj.get("startup_prompt") or "").strip() or item_text
        props.append(Proposal(
            item_index=idx,
            item_text=item_text,
            role=role,
            directory=directory,
            startup_prompt=prompt,
            reason=obj.get("reason", ""),
            unresolved=directory not in dir_set,
        ))
    props.sort(key=lambda p: p.item_index)
    return props


def classify(items: list[str], role_names: list[str], directories: list[str],
             client) -> list[Proposal]:
    payload = build_user_payload(items, role_names, directories)
    last_error: Exception | None = None
    for _ in range(2):  # one initial attempt + one retry
        text = client.complete(SYSTEM_PROMPT, payload)
        try:
            return parse_response(text, items, role_names, directories)
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            last_error = exc
    raise ValueError(f"Triage returned unparseable output: {last_error}")
