import pytest
from dispatch_hub.anthropic_client import resolve_api_key, NoApiKey


def test_env_var_takes_precedence():
    env = {"ANTHROPIC_API_KEY": "env-key"}
    assert resolve_api_key({"anthropic_api_key": "settings-key"}, environ=env) == "env-key"


def test_falls_back_to_settings_key():
    assert resolve_api_key({"anthropic_api_key": "settings-key"}, environ={}) == "settings-key"


def test_raises_when_no_key_anywhere():
    with pytest.raises(NoApiKey):
        resolve_api_key({}, environ={})


def test_blank_env_value_is_ignored():
    env = {"ANTHROPIC_API_KEY": ""}
    assert resolve_api_key({"anthropic_api_key": "settings-key"}, environ=env) == "settings-key"
