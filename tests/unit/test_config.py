"""Tests for the configuration module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from core.config import ConfigLoader, NATSSettings, OracleSettings, SettingsSerializer
from core.errors import ConfigError, ConfigNotFoundError


class TestOracleSettings:
    def test_defaults(self) -> None:
        settings = OracleSettings()
        assert settings.environment == "development"
        assert settings.log_level == "INFO"
        assert settings.nats.url == "nats://localhost:4222"

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ORACLE_NATS__URL", "nats://test:4222")
        settings = OracleSettings()
        assert settings.nats.url == "nats://test:4222"

    def test_invalid_environment_raises(self) -> None:
        with pytest.raises(ValidationError):
            OracleSettings(environment="invalid")

    def test_invalid_log_level_raises(self) -> None:
        with pytest.raises(ValidationError):
            OracleSettings(log_level="TRACE")

    def test_valid_production(self) -> None:
        settings = OracleSettings(environment="production", log_level="WARNING")
        assert settings.environment == "production"

    def test_nats_timeout_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            OracleSettings(nats=NATSSettings(timeout=-1))


class TestConfigLoader:
    def test_load_defaults_when_no_file(self, tmp_path: Path) -> None:
        loader = ConfigLoader(tmp_path)
        settings = loader.load()
        assert settings.environment == "development"

    def test_load_yaml_override(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        yaml_file = config_dir / "development.yaml"
        yaml_file.write_text(
            yaml.safe_dump({"log_level": "DEBUG", "nats": {"url": "nats://override:4222"}})
        )

        loader = ConfigLoader(config_dir)
        settings = loader.load()
        assert settings.log_level == "DEBUG"
        assert settings.nats.url == "nats://override:4222"
        assert settings.environment == "development"  # default preserved

    def test_validate_existing_file(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml.safe_dump({"log_level": "DEBUG"}))
        loader = ConfigLoader(tmp_path)
        settings = loader.validate(str(yaml_file))
        assert settings.log_level == "DEBUG"

    def test_validate_missing_file_raises(self) -> None:
        loader = ConfigLoader(Path("/nonexistent"))
        with pytest.raises(ConfigNotFoundError):
            loader.validate("/nonexistent/config.yaml")

    def test_load_invalid_yaml_raises(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("{invalid: yaml: : : }")
        loader = ConfigLoader(tmp_path)
        with pytest.raises(ConfigError):
            loader._load_yaml(yaml_file)


class TestSettingsSerializer:
    def test_to_json_roundtrip(self) -> None:
        settings = OracleSettings()
        data = json.loads(SettingsSerializer.to_json(settings))
        assert data["environment"] == "development"
        assert data["nats"]["url"] == "nats://localhost:4222"

    def test_to_yaml_roundtrip(self) -> None:
        settings = OracleSettings(log_level="DEBUG")
        yaml_out = SettingsSerializer.to_yaml(settings)
        parsed = yaml.safe_load(yaml_out)
        assert parsed["log_level"] == "DEBUG"

    def test_write_json(self, tmp_path: Path) -> None:
        settings = OracleSettings()
        path = SettingsSerializer.write_json(settings, tmp_path / "config.json")
        assert path.exists()
        assert json.loads(path.read_text())["environment"] == "development"

    def test_write_yaml(self, tmp_path: Path) -> None:
        settings = OracleSettings()
        path = SettingsSerializer.write_yaml(settings, tmp_path / "config.yaml")
        assert path.exists()
        assert yaml.safe_load(path.read_text())["log_level"] == "INFO"

    def test_to_toml_missing_dep_raises(self) -> None:
        settings = OracleSettings()
        with pytest.raises(RuntimeError, match="tomli_w"):
            SettingsSerializer.to_toml(settings)
