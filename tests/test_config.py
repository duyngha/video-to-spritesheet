"""Tests for the tiny persisted config."""
from __future__ import annotations

from videotosprite.core import config


def test_roundtrip_and_default(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    assert config.get("out_dir") is None            # nothing yet
    assert config.get("out_dir", "x") == "x"        # default honoured
    config.set("out_dir", "/some/where")
    assert config.get("out_dir") == "/some/where"   # persisted
    config.set("open_dir", "/videos")
    assert config.load() == {"out_dir": "/some/where", "open_dir": "/videos"}


def test_corrupt_config_falls_back_to_empty(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text("{ not valid json")
    monkeypatch.setattr(config, "CONFIG_PATH", path)
    assert config.load() == {}                       # silently ignored
    assert config.get("anything", 42) == 42
