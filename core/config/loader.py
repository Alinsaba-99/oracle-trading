"""ConfigLoader — layered YAML config with env overrides."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core.config.settings import OracleSettings
from core.errors import ConfigError, ConfigNotFoundError


class ConfigLoader:
    """Loads and merges config from YAML with env var override via pydantic-settings."""

    def __init__(self, config_dir: str | Path = "config") -> None:
        self.config_dir = Path(config_dir)

    def load(self, profile: str = "development") -> OracleSettings:
        """Load config/{profile}.yaml on top of defaults, then env override."""
        base = OracleSettings()
        yaml_path = self.config_dir / f"{profile}.yaml"

        if yaml_path.exists():
            overrides = self._load_yaml(yaml_path)
            merged = base.model_dump()
            self._deep_merge(merged, overrides)
            return OracleSettings(**merged)

        return base

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        """Load and parse a YAML config file."""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in {path}: {e}", code="CFG_YAML_PARSE") from e

    def validate(self, path: str | Path) -> OracleSettings:
        """Validate a config file. Raises on missing file or invalid schema."""
        p = Path(path)
        if not p.exists():
            raise ConfigNotFoundError(f"Config file not found: {p}")
        data = self._load_yaml(p)
        return OracleSettings(**data)

    @staticmethod
    def _deep_merge(base: dict[str, object], override: dict[str, object]) -> None:
        """Recursively merge override into base (mutates base)."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                ConfigLoader._deep_merge(
                    base[key],  # type: ignore[arg-type]
                    value,
                )
            else:
                base[key] = value
