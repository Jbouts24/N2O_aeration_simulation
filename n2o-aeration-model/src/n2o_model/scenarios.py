"""Scenario and configuration loading utilities."""
from __future__ import annotations

from pathlib import Path

from .parameters import ModelConfig
from .utils import deep_merge, load_yaml



def _load_yaml_with_extends(path: Path) -> dict:
    raw = load_yaml(path)
    extends = raw.pop("extends", None)
    if not extends:
        return raw

    base_path = (path.parent / extends).resolve()
    base_raw = _load_yaml_with_extends(base_path)
    return deep_merge(base_raw, raw)



def load_config(path: str | Path) -> ModelConfig:
    path = Path(path).resolve()
    raw = _load_yaml_with_extends(path)
    return ModelConfig.from_dict(raw)
