from __future__ import annotations

import json
from dataclasses import dataclass

DEFAULT_MODEL = "claude-sonnet-4-6"
NONE_ROLE = "(none)"

SYSTEM_PROMPT = (
    "You assign software work items to a role, a project directory, and a concrete "
    "startup prompt for a coding agent. You are given a list of items (each with an "
    "index), a list of allowed role names, a list of allowed project directories, and "
    "a list of allowed parent folders. For every item return one object. 'role' MUST "
    "be exactly one of the allowed role names, or the string '(none)' if none fit. "
    "If the item fits an existing project, 'directory' MUST be exactly one of the "
    "allowed directories and 'is_new_project' MUST be false. If the item describes "
    "starting a NEW project that matches none of the allowed directories, set "
    "'is_new_project' to true, leave 'directory' empty, set 'new_dir_slug' to a short "
    "folder name for it, set 'suggested_parent' to the best-fitting allowed parent, "
    "and write a 'startup_prompt' that tells the agent to scaffold and brainstorm the "
    "project from scratch (the directory will be empty). 'startup_prompt' is otherwise "
    "a clear first instruction, expanded from the terse item into something actionable. "
    "'reason' is one short phrase. Respond with ONLY a JSON array of objects with keys: "
    "item_index, role, directory, is_new_project, new_dir_slug, suggested_parent, "
    "startup_prompt, reason. No prose, no markdown fences."
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
    is_new_project: bool = False
    new_dir_slug: str = ""
    suggested_parent: str = ""


def build_user_payload(items: list[str], role_names: list[str],
                       directories: list[str], parents: list[str] | None = None) -> str:
    return json.dumps({
        "items": [{"index": i, "text": t} for i, t in enumerate(items)],
        "allowed_roles": role_names,
        "allowed_directories": directories,
        "allowed_parents": parents or [],
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
        role = None if raw_role == NONE_ROLE or raw_role not in role_set else raw_role
        directory = obj.get("directory", "") or ""
        prompt = (obj.get("startup_prompt") or "").strip() or item_text
        is_new = bool(obj.get("is_new_project", False))
        props.append(Proposal(
            item_index=idx,
            item_text=item_text,
            role=role,
            directory=directory,
            startup_prompt=prompt,
            reason=obj.get("reason", ""),
            unresolved=(False if is_new else directory not in dir_set),
            is_new_project=is_new,
            new_dir_slug=(obj.get("new_dir_slug") or "").strip(),
            suggested_parent=(obj.get("suggested_parent") or "").strip(),
        ))
    props.sort(key=lambda p: p.item_index)
    return props


def classify(items: list[str], role_names: list[str], directories: list[str],
             client, parents: list[str] | None = None) -> list[Proposal]:
    payload = build_user_payload(items, role_names, directories, parents)
    last_error: Exception | None = None
    for _ in range(2):  # one initial attempt + one retry
        text = client.complete(SYSTEM_PROMPT, payload)
        try:
            return parse_response(text, items, role_names, directories)
        except (json.JSONDecodeError, KeyError, ValueError, TypeError, IndexError) as exc:
            last_error = exc
    raise ValueError(f"Triage returned unparseable output: {last_error}")
