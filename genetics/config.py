"""GA configuration module — canonical import point for all config types.

Usage:

    from genetics.config import GAConfig, GenomeConfig, WalkForwardConfig
"""

from __future__ import annotations

from genetics.engine import GAConfig, GAResult
from genetics.fitness import WalkForwardConfig
from genetics.genome.signal import GenomeConfig
from genetics.islands import MigrationPolicy

__all__ = ["GAConfig", "GAResult", "GenomeConfig", "MigrationPolicy", "WalkForwardConfig"]
