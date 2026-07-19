"""ConfigLoader — layered YAML config with env overrides."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from core.config.settings import OracleSettings
from core.errors import ConfigError, ConfigNotFoundError


class ConfigLoader:
    """Loads and merges config from YAML with env var override via pydantic-settings."""

    def __init__(self, config_dir: str | Path = "config") -> None:
        self.config_dir = Path(config_dir)

    def load(self, profile: str = "development") -> OracleSettings:
        """Load config/{profile}.yaml on top of defaults, then env override.

        Priority order (highest last):
        1. pydantic field defaults
        2. YAML config file
        3. Environment variables (ORACLE_*)
        """
        base = OracleSettings()
        yaml_path = self.config_dir / f"{profile}.yaml"

        if yaml_path.exists():
            overrides = self._load_yaml(yaml_path)
            merged = base.model_dump()
            self._deep_merge(merged, overrides)
            # BaseSettings(model_dump=...) would let explicit kwargs override env.
            # Instead, we apply YAML values first, then let env vars override.
            # model_construct skips env loading, so we create via model_validate
            # which re-reads env vars on top of the merged dict.
            import os as _os

            env_overrides = {}
            for key in merged:
                env_key = f"ORACLE_{key.upper()}"
                if env_key in _os.environ:
                    env_overrides[key] = _os.environ[env_key]
            if env_overrides:
                self._deep_merge(merged, env_overrides)  # type: ignore[arg-type]
            return OracleSettings(**merged)

        return base

    @staticmethod
    def _expand_vars(value: object) -> object:
        """Recursively expand ``${VAR}`` or ``${VAR:default}`` in string values."""
        import os as _os
        import re as _re

        if isinstance(value, str):

            def _replace(m: _re.Match[str]) -> str:
                var = m.group(1)
                default = m.group(2)
                resolved = _os.environ.get(var)
                if resolved is not None:
                    return resolved
                if default is not None:
                    return default
                return m.group(0)  # leave as-is if not found

            return _re.sub(r"\$\{([^}:]+)(?::([^}]*))?\}", _replace, value)
        if isinstance(value, dict):
            return {k: ConfigLoader._expand_vars(v) for k, v in value.items()}
        if isinstance(value, list):
            return [ConfigLoader._expand_vars(v) for v in value]
        return value

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        """Load and parse a YAML config file, expanding env vars."""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            result = data if isinstance(data, dict) else {}
            expanded = self._expand_vars(result)
            return cast(dict[str, Any], expanded)
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
