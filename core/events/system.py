"""System event models and subject constants."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ── Subject constants ──────────────────────────────────────────────

SYSTEM_HEALTH = "system.health"
SYSTEM_PLUGIN_REGISTERED = "system.plugin.registered"

# ── Payload models ────────────────────────────────────────────────


class SystemEventPayload(BaseModel):
    """Base payload for system events."""

    timestamp: datetime = Field(default_factory=datetime.now)
    service: str = "oracle"


class HealthEventPayload(SystemEventPayload):
    """Payload for ``system.health`` events."""

    status: Literal["healthy", "degraded", "unhealthy"]
    components: dict[str, str]


class PluginRegisteredPayload(SystemEventPayload):
    """Payload for ``system.plugin.registered`` events."""

    plugin_name: str
    plugin_version: str
