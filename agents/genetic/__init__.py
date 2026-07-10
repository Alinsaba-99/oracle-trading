"""Genetic algorithm strategist bridge — Phase 3 GA to Phase 4 MAS."""

from __future__ import annotations

from agents.genetic.adapter import GAAdapter, StrategySuggestion
from agents.genetic.registry import GARegistryReader
from agents.genetic.strategist import GeneticStrategist

__all__ = ["GAAdapter", "GARegistryReader", "GeneticStrategist", "StrategySuggestion"]
