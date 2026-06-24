from __future__ import annotations

import os

_ENV_KEY = "ANTHROPIC_API_KEY"


class NoApiKey(RuntimeError):
    """No Anthropic API key could be resolved from env or settings."""


def resolve_api_key(settings: dict, environ=os.environ) -> str:
    env_val = (environ.get(_ENV_KEY) or "").strip()
    if env_val:
        return env_val
    settings_val = (settings.get("anthropic_api_key") or "").strip()
    if settings_val:
        return settings_val
    raise NoApiKey(
        f"No Anthropic API key. Set the {_ENV_KEY} environment variable, "
        "or add 'anthropic_api_key' to config/settings.json."
    )


class TriageClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def complete(self, system: str, user: str) -> str:
        from anthropic import Anthropic  # lazy: keeps the package importable without the SDK

        client = Anthropic(api_key=self.api_key)
        msg = client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in msg.content if getattr(block, "type", None) == "text")
