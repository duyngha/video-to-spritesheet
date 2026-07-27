"""Tiny persistent config (last-used folders, etc.) stored as JSON in the user's
home so dialogs reopen where you left off. All operations fail silently — a
missing or corrupt config just means defaults."""
from __future__ import annotations

import json
from pathlib import Path

CONFIG_PATH = Path.home() / ".videotosprite" / "config.json"


def load() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception:
        return {}


def save(data: dict) -> None:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def get(key: str, default=None):
    return load().get(key, default)


def set(key: str, value) -> None:
    data = load()
    data[key] = value
    save(data)
