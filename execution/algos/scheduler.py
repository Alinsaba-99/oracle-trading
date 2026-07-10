"""Shared scheduling logic for time/volume-based algos."""

from __future__ import annotations

from decimal import Decimal


class AlgoScheduler:
    """Shared scheduling logic for time/volume-based algos."""

    @staticmethod
    def time_slices(total_seconds: int, n_slices: int) -> list[int]:
        """Divide total_seconds into n_slices equal intervals."""
        if n_slices <= 0:
            return [total_seconds]
        slice_size = total_seconds // n_slices
        return [slice_size] * n_slices

    @staticmethod
    def volume_slices(
        total_quantity: Decimal,
        volume_profile: list[float],
        n_slices: int,
    ) -> list[Decimal]:
        """Divide total_quantity according to volume profile."""
        if not volume_profile or n_slices <= 0:
            return [total_quantity]
        profile = volume_profile[:n_slices]
        total = sum(profile)
        if total <= 0:
            return [total_quantity / n_slices] * n_slices
        return [
            Decimal(str(round(p / total * float(total_quantity), 4)))
            for p in profile
        ]
