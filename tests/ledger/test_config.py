import json

from ledger.config import Config, load


def test_load_creates_default_file_when_missing(tmp_path):
    p = tmp_path / "config.json"
    cfg = load(p)
    assert p.exists()
    assert cfg.daily_usage_budget == 0.0  # off by default
    assert "node" in cfg.ai_process_names


def test_load_merges_partial_and_ignores_unknown(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"daily_usage_budget": 5_000_000.0, "mystery": 1}), encoding="utf-8")
    cfg = load(p)
    assert cfg.daily_usage_budget == 5_000_000.0
    assert cfg.warn_ratio == 0.8  # default preserved
