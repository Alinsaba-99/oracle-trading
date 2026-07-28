"""Tests for analytics.strategy.regime_ensemble — regime-aware routing."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from analytics.strategy.regime_ensemble import (
    RegimeAwareEnsemble,
    RegimeLabel,
    SpecialistId,
    _sma_regime_heuristic,
)


def _make_df(close: list[float]) -> pl.DataFrame:
    n = len(close)
    return pl.DataFrame(
        {
            "close": close,
            "high": [c + 0.5 for c in close],
            "low": [c - 0.5 for c in close],
            "open": close,
            "volume": [1000.0] * n,
        }
    )


class _MockSpecialist:
    """Returns a constant signal series."""

    def __init__(self, value: int) -> None:
        self.value = value
        self.calls = 0

    def compute(self, data: pl.DataFrame) -> pl.Series:
        self.calls += 1
        return pl.Series("signal", [self.value] * len(data), dtype=pl.Int8)


class _MockDetector:
    def __init__(self, label: str, confidence: float) -> None:
        self.label = label
        self.confidence = confidence

    def detect(self, data: pl.DataFrame) -> tuple[str, float]:  # noqa: ARG002
        return self.label, self.confidence


class TestRouting:
    """Routing logic must respect regime → specialist map."""

    def test_bull_routes_to_trend(self) -> None:
        df = _make_df(list(np.linspace(100, 130, 100)))
        ens = RegimeAwareEnsemble(
            specialists={SpecialistId.TREND: _MockSpecialist(1)},
            regime_detector=_MockDetector("bull", 0.9),
        )
        d = ens.route(df)
        assert d.specialist == SpecialistId.TREND
        assert d.regime == RegimeLabel.BULL

    def test_choppy_routes_to_mean_reversion(self) -> None:
        df = _make_df(list(np.linspace(100, 101, 100)))
        ens = RegimeAwareEnsemble(
            specialists={SpecialistId.MEAN_REVERSION: _MockSpecialist(0)},
            regime_detector=_MockDetector("choppy", 0.8),
        )
        d = ens.route(df)
        assert d.specialist == SpecialistId.MEAN_REVERSION

    def test_volatile_routes_to_breakout(self) -> None:
        df = _make_df(list(np.linspace(100, 105, 100)))
        ens = RegimeAwareEnsemble(
            specialists={SpecialistId.BREAKOUT: _MockSpecialist(1)},
            regime_detector=_MockDetector("volatile", 0.9),
        )
        d = ens.route(df)
        assert d.specialist == SpecialistId.BREAKOUT

    def test_low_confidence_goes_flat(self) -> None:
        df = _make_df(list(np.linspace(100, 130, 100)))
        ens = RegimeAwareEnsemble(
            specialists={SpecialistId.TREND: _MockSpecialist(1)},
            regime_detector=_MockDetector("bull", 0.3),  # below 0.5 default
            min_confidence=0.5,
        )
        d = ens.route(df)
        assert d.specialist == SpecialistId.FLAT

    def test_unknown_regime_goes_flat(self) -> None:
        df = _make_df(list(np.linspace(100, 105, 100)))
        ens = RegimeAwareEnsemble(
            specialists={SpecialistId.TREND: _MockSpecialist(1)},
            regime_detector=_MockDetector("unknown", 0.9),
        )
        d = ens.route(df)
        assert d.specialist == SpecialistId.FLAT

    def test_missing_specialist_falls_back_to_next(self) -> None:
        """BULL routes to trend, then breakout — if trend missing, breakout."""
        df = _make_df(list(np.linspace(100, 130, 100)))
        ens = RegimeAwareEnsemble(
            specialists={SpecialistId.BREAKOUT: _MockSpecialist(1)},
            regime_detector=_MockDetector("bull", 0.9),
        )
        d = ens.route(df)
        assert d.specialist == SpecialistId.BREAKOUT

    def test_no_specialist_available_goes_flat(self) -> None:
        df = _make_df(list(np.linspace(100, 130, 100)))
        ens = RegimeAwareEnsemble(
            specialists={SpecialistId.LORENTZIAN: _MockSpecialist(1)},  # not routed from bull
            regime_detector=_MockDetector("bull", 0.9),
        )
        d = ens.route(df)
        assert d.specialist == SpecialistId.FLAT


class TestCompute:
    """compute() must dispatch to the right specialist."""

    def test_dispatches_to_selected_specialist(self) -> None:
        df = _make_df(list(np.linspace(100, 130, 100)))
        trend = _MockSpecialist(1)
        breakout = _MockSpecialist(-1)
        ens = RegimeAwareEnsemble(
            specialists={SpecialistId.TREND: trend, SpecialistId.BREAKOUT: breakout},
            regime_detector=_MockDetector("bull", 0.9),
        )
        sig = ens.compute(df)
        assert trend.calls == 1
        assert breakout.calls == 0
        assert set(sig.to_numpy()) == {1}

    def test_flat_decision_returns_zeros(self) -> None:
        df = _make_df(list(np.linspace(100, 130, 100)))
        trend = _MockSpecialist(1)
        ens = RegimeAwareEnsemble(
            specialists={SpecialistId.TREND: trend},
            regime_detector=_MockDetector("bull", 0.1),  # very low confidence
            min_confidence=0.5,
        )
        sig = ens.compute(df)
        assert trend.calls == 0
        assert set(sig.to_numpy()) == {0}

    def test_registered_specialist_actually_used(self) -> None:
        df = _make_df(list(np.linspace(100, 130, 100)))
        mr = _MockSpecialist(-1)
        ens = RegimeAwareEnsemble(
            specialists={SpecialistId.MEAN_REVERSION: mr},
            regime_detector=_MockDetector("choppy", 0.85),
        )
        sig = ens.compute(df)
        assert mr.calls == 1
        assert set(sig.to_numpy()) == {-1}


class TestHeuristic:
    """The default SMA heuristic must produce sensible regimes."""

    def test_short_series_returns_unknown(self) -> None:
        df = _make_df([100.0, 101.0, 102.0])
        ens = RegimeAwareEnsemble(specialists={SpecialistId.TREND: _MockSpecialist(1)})
        d = ens.route(df)
        assert d.regime == RegimeLabel.UNKNOWN
        assert d.specialist == SpecialistId.FLAT

    def test_empty_specialists_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            RegimeAwareEnsemble(specialists={})

    def test_detector_failure_falls_back(self) -> None:
        df = _make_df(list(np.linspace(100, 130, 100)))

        class _Bad:
            def detect(self, data: pl.DataFrame) -> tuple[str, float]:  # noqa: ARG002
                raise RuntimeError("boom")

        ens = RegimeAwareEnsemble(
            specialists={SpecialistId.TREND: _MockSpecialist(1)}, regime_detector=_Bad()
        )
        d = ens.route(df)
        # Falls back to heuristic — should still produce a decision
        assert d.regime in set(RegimeLabel)

    def test_confidence_always_clears_routing_gate(self) -> None:
        """Any reported regime must be actionable.

        The gates scaled confidence so a freshly-triggered trend scored ~0.33,
        below the 0.5 routing threshold — the regime was detected and then
        immediately forced FLAT, so no trend specialist could ever run.
        """
        rng = np.random.default_rng(7)
        for scale in (0.2, 1.0, 4.0):
            for drift in (-0.4, 0.0, 0.4):
                close = list(100 + np.cumsum(rng.standard_normal(260) * scale + drift))
                label, conf = _sma_regime_heuristic(_make_df(close))
                if label is not RegimeLabel.UNKNOWN:
                    assert conf >= 0.5, f"{label} scored {conf:.3f} (scale={scale}, drift={drift})"

    def test_trend_detection_is_timeframe_invariant(self) -> None:
        """The same shape at different bar sizes must classify the same.

        Gates used to be absolute percentage moves tuned on daily bars, so on
        finer bars — where per-bar moves are proportionally smaller — nearly
        everything read as choppy (~92% on EURUSD 1h) and the trend
        specialists were starved. Gates are now scaled by realized vol, so
        rescaling per-bar volatility must not change the verdict.
        """
        rng = np.random.default_rng(11)
        steps = rng.standard_normal(260)
        labels = set()
        for scale in (0.05, 0.25, 1.0, 5.0):
            # Same path shape, only per-bar amplitude differs — as when the
            # identical trend is sampled at 1h vs 1d.
            close = list(100 + np.cumsum(steps * scale + 0.35 * scale))
            label, _conf = _sma_regime_heuristic(_make_df(close))
            labels.add(label)
        assert len(labels) == 1, f"verdict changed with bar scale: {labels}"


class TestLorentzianIntegration:
    """Lorentzian specialist must be wired post-causal-fix."""

    def test_lorentzian_specialist_callable(self) -> None:
        from analytics.strategy.lorentzian import LorentzianKNN

        rng = np.random.default_rng(0)
        close = list(100 + np.cumsum(rng.standard_normal(150) * 0.5))
        df = _make_df(close)
        knn = LorentzianKNN(k=4, lookahead=4, max_bars_back=80, feature_count=3)
        ens = RegimeAwareEnsemble(
            specialists={SpecialistId.LORENTZIAN: knn},
            regime_detector=_MockDetector("choppy", 0.85),
        )
        sig = ens.compute(df)
        # Lorentzian returns Int8 signals (0 or 1 in long_only mode)
        vals = set(sig.to_numpy().tolist())
        assert vals.issubset({-1, 0, 1})
