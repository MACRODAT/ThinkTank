"""
core/config.py — Configuration loader with dot-access.
"""
from __future__ import annotations
import yaml
from pathlib import Path
from typing import Any


class DotDict:
    def __init__(self, data: dict):
        for key, value in data.items():
            if isinstance(value, dict):
                setattr(self, key, DotDict(value))
            else:
                setattr(self, key, value)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __repr__(self):
        return f"DotDict({self.__dict__})"


def _load_config() -> DotDict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)
    return DotDict(raw)


config = _load_config()
