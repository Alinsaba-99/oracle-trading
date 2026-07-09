"""SettingsSerializer — export OracleSettings to JSON, YAML, or TOML."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from core.config.settings import OracleSettings


class SettingsSerializer:
    """Export OracleSettings to portable formats."""

    @staticmethod
    def _data(settings: OracleSettings) -> dict[str, object]:
        return settings.model_dump(mode="json")

    @staticmethod
    def to_json(settings: OracleSettings, indent: int = 2) -> str:
        return json.dumps(SettingsSerializer._data(settings), indent=indent)

    @staticmethod
    def to_yaml(settings: OracleSettings) -> str:
        result: str = yaml.safe_dump(
            SettingsSerializer._data(settings), default_flow_style=False, sort_keys=False
        )
        return result

    @staticmethod
    def to_toml(settings: OracleSettings) -> str:
        """Export to TOML. Raises RuntimeError if tomli_w is not installed."""
        try:
            import tomli_w
        except ImportError:
            raise RuntimeError(
                "tomli_w is required for TOML export. Install: pip install tomli-w"
            ) from None
        data: str = tomli_w.dumps(SettingsSerializer._data(settings))
        return data

    @staticmethod
    def write_json(settings: OracleSettings, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(SettingsSerializer.to_json(settings))
        return p

    @staticmethod
    def write_yaml(settings: OracleSettings, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(SettingsSerializer.to_yaml(settings))
        return p

    @staticmethod
    def write_toml(settings: OracleSettings, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(SettingsSerializer.to_toml(settings))
        return p
