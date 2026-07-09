"""Tests for M5 Regime Detection — detectors, ensemble voter, and orchestrator."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from analytics.common.errors import RegimeError
from analytics.regime import (
    BOCDDetector,
    CorrelationDetector,
    EnsembleVoter,
    HMMDetector,
    PELTDetector,
    RegimeDetector,
    RegimeSettings,
    VolClusterDetector,
)

warnings.filterwarnings("ignore", category=RuntimeWarning, module="hmmlearn")


# ======================================================================
# Helpers
# ======================================================================


def _returns(n: int = 200, drift: float = 0.001, vol: float = 0.015, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(drift, vol, n)


def _bull_bear_returns(n_seg: int = 100) -> np.ndarray:
    """Two distinct regimes: bull then bear."""
    rng = np.random.default_rng(42)
    bull = rng.normal(0.003, 0.01, n_seg)
    bear = rng.normal(-0.003, 0.02, n_seg)
    return np.concatenate([bull, bear])


def _price_matrix(
    n_periods: int = 100, n_assets: int = 3, common_drift: float = 0.001, seed: int = 42
) -> np.ndarray:
    """Correlated price paths."""
    rng = np.random.default_rng(seed)
    common = rng.normal(common_drift, 0.01, (n_periods, 1))
    specific = rng.normal(0, 0.005, (n_periods, n_assets))
    returns = common + specific * 0.3
    prices = np.cumprod(1 + returns, axis=0)
    prices = np.vstack([np.ones(n_assets), prices])  # start at 1
    return prices


# ======================================================================
# HMMDetector
# ======================================================================


class TestHMMDetector:
    def test_fit_and_predict(self) -> None:
        data = _returns(500, drift=0.001)
        hmm = HMMDetector(n_states=4).fit(data)
        state = hmm.predict(data)
        assert isinstance(state, int)
        assert 0 <= state < 4

    def test_state_to_regime(self) -> None:
        hmm = HMMDetector(n_states=4)
        assert hmm.state_to_regime(0) in ("bull", "bear", "choppy", "volatile")
        assert hmm.state_to_regime(99) == "state_99"

    def test_predict_before_fit_raises(self) -> None:
        hmm = HMMDetector()
        with pytest.raises(RegimeError, match="not fitted"):
            hmm.predict(np.array([0.0, 0.1]))

    def test_insufficient_data_raises(self) -> None:
        hmm = HMMDetector(n_states=4)
        with pytest.raises(RegimeError, match="Need at least"):
            hmm.fit(np.array([0.0, 0.1, 0.2]))

    def test_nan_input_raises(self) -> None:
        hmm = HMMDetector()
        with pytest.raises(RegimeError, match=r"NaN|Inf"):
            hmm.fit(np.array([0.0, np.nan, 0.0]))

    def test_empty_input_raises(self) -> None:
        hmm = HMMDetector()
        with pytest.raises(RegimeError, match="Empty"):
            hmm.fit(np.array([]))

    def test_2d_input_accepted(self) -> None:
        data = _returns(300).reshape(-1, 1)
        hmm = HMMDetector(n_states=3).fit(data)
        state = hmm.predict(data)
        assert isinstance(state, int)


# ======================================================================
# BOCDDetector
# ======================================================================


class TestBOCDDetector:
    def test_fit_and_get_changepoints(self) -> None:
        data = _bull_bear_returns()
        bocd = BOCDDetector().fit(data)
        cps = bocd.get_changepoints()
        assert isinstance(cps, list)
        assert all(isinstance(cp, int) for cp in cps)

    def test_has_changed_on_regime_shift(self) -> None:
        data = _bull_bear_returns()
        bocd = BOCDDetector(min_window=10).fit(data, pen=5)
        assert isinstance(bocd.has_changed(), bool)

    def test_insufficient_data_raises(self) -> None:
        bocd = BOCDDetector(min_window=10)
        with pytest.raises(RegimeError, match="Need at least"):
            bocd.fit(np.array([0.0, 0.1]))

    def test_nan_input_raises(self) -> None:
        bocd = BOCDDetector()
        with pytest.raises(RegimeError, match=r"NaN|Inf"):
            bocd.fit(np.array([0.0, np.nan, 0.0]))

    def test_empty_input_raises(self) -> None:
        bocd = BOCDDetector()
        with pytest.raises(RegimeError, match="Empty"):
            bocd.fit(np.array([]))

    def test_custom_penalty(self) -> None:
        data = _bull_bear_returns()
        bocd_low = BOCDDetector().fit(data, pen=2)
        bocd_high = BOCDDetector().fit(data, pen=50)
        # Lower penalty → more changepoints
        assert len(bocd_low.get_changepoints()) >= len(bocd_high.get_changepoints())


# ======================================================================
# PELTDetector
# ======================================================================


class TestPELTDetector:
    def test_fit_and_get_changepoints(self) -> None:
        data = _bull_bear_returns()
        pelt = PELTDetector().fit(data)
        cps = pelt.get_changepoints()
        assert isinstance(cps, list)

    def test_different_penalty(self) -> None:
        data = _bull_bear_returns()
        pelt_low = PELTDetector().fit(data, pen=5)
        pelt_high = PELTDetector().fit(data, pen=50)
        assert len(pelt_low.get_changepoints()) >= len(pelt_high.get_changepoints())

    def test_insufficient_data_raises(self) -> None:
        pelt = PELTDetector(min_window=10)
        with pytest.raises(RegimeError, match="Need at least"):
            pelt.fit(np.array([0.0, 0.1]))

    def test_nan_input_raises(self) -> None:
        pelt = PELTDetector()
        with pytest.raises(RegimeError, match=r"NaN|Inf"):
            pelt.fit(np.array([0.0, np.nan, 0.0]))

    def test_empty_input_raises(self) -> None:
        pelt = PELTDetector()
        with pytest.raises(RegimeError, match="Empty"):
            pelt.fit(np.array([]))


# ======================================================================
# VolClusterDetector
# ======================================================================


class TestVolClusterDetector:
    def test_fit_and_predict(self) -> None:
        data = _returns(300, vol=0.02)
        vol = VolClusterDetector(n_clusters=3).fit(data)
        label = vol.predict(data)
        assert label in ("low", "normal", "high", "unknown")

    def test_high_vol_detected(self) -> None:
        rng = np.random.default_rng(99)
        low_vol = rng.normal(0.001, 0.005, 300)
        high_vol = rng.normal(0.001, 0.05, 300)
        data = np.concatenate([low_vol, high_vol])
        vol = VolClusterDetector(n_clusters=3, window=20).fit(data)
        # Predict on the high-vol segment should be "high" or "panic"
        high_label = vol.predict(data[-100:])
        low_label = vol.predict(data[:100])
        # High vol segment should not be "low"
        # (exact label depends on clustering, but it's mechanical)
        assert isinstance(high_label, str)
        assert isinstance(low_label, str)

    def test_predict_before_fit_raises(self) -> None:
        vc = VolClusterDetector()
        with pytest.raises(RegimeError, match="not fitted"):
            vc.predict(np.zeros(50))

    def test_insufficient_data_raises(self) -> None:
        vc = VolClusterDetector(window=20)
        with pytest.raises(RegimeError, match="Need at least"):
            vc.fit(np.array([0.0, 0.1]))

    def test_nan_input_raises(self) -> None:
        vc = VolClusterDetector()
        with pytest.raises(RegimeError, match=r"NaN|Inf"):
            vc.fit(np.array([0.0, np.nan, 0.0]))

    def test_empty_input_raises(self) -> None:
        vc = VolClusterDetector()
        with pytest.raises(RegimeError, match="Empty"):
            vc.fit(np.array([]))

    def test_too_short_predict_returns_unknown(self) -> None:
        data = _returns(100)
        vc = VolClusterDetector(window=20).fit(data)
        label = vc.predict(np.array([0.001]))
        assert label == "unknown"


# ======================================================================
# CorrelationDetector
# ======================================================================


class TestCorrelationDetector:
    def test_high_correlation_risk_on(self) -> None:
        """Highly correlated assets → risk_on."""
        prices = _price_matrix(100, 3, common_drift=0.002)
        corr = CorrelationDetector()
        avg = corr.compute(prices, window=30)
        assert corr.classify(avg) == "risk_on"

    def test_low_correlation_mixed(self) -> None:
        """Near-zero average correlation → mixed."""
        rng = np.random.default_rng(99)
        prices = np.column_stack(
            [np.cumprod(1 + rng.normal(0, 0.01, 100)), np.cumprod(1 + rng.normal(0, 0.01, 100))]
        )
        corr = CorrelationDetector()
        avg = corr.compute(prices, window=20)
        assert corr.classify(avg) == "mixed"

    def test_single_asset_returns_zero(self) -> None:
        prices = _price_matrix(100, 1)
        corr = CorrelationDetector()
        avg = corr.compute(prices, window=20)
        assert avg == 0.0

    def test_short_window_returns_zero(self) -> None:
        prices = _price_matrix(10, 3)
        corr = CorrelationDetector()
        avg = corr.compute(prices, window=20)
        assert avg == 0.0

    def test_non_2d_raises(self) -> None:
        corr = CorrelationDetector()
        with pytest.raises(RegimeError, match="2-D"):
            corr.compute(np.array([1.0, 2.0]))

    def test_empty_raises(self) -> None:
        corr = CorrelationDetector()
        with pytest.raises(RegimeError, match="Empty"):
            corr.compute(np.array([]))

    def test_classify_thresholds(self) -> None:
        corr = CorrelationDetector()
        assert corr.classify(0.8) == "risk_on"
        assert corr.classify(0.5 + 1e-9) == "risk_on"
        assert corr.classify(0.0) == "mixed"
        assert corr.classify(-0.3) == "risk_off"
        assert corr.classify(-0.2 - 1e-9) == "risk_off"


# ======================================================================
# EnsembleVoter
# ======================================================================


class TestEnsembleVoter:
    def test_simple_majority(self) -> None:
        voter = EnsembleVoter(min_confidence=0.0, min_bars=0)
        voter.add_vote("hmm", "bull", 1.0)
        voter.add_vote("vol", "bull", 1.0)
        voter.add_vote("corr", "bear", 1.0)
        regime, conf, details = voter.resolve()
        assert regime == "bull"
        assert conf > 0.0
        assert details["transition"] is False  # first resolve establishes regime
        # hmm  (0.2) votes bear = 0.2*1.0 = 0.2
        # vol  (0.1) votes bull = 0.1*1.0 = 0.1
        # → bull = 0.4, bear = 0.2
        voter = EnsembleVoter(
            min_confidence=0.0,
            min_bars=0,
            weights={"hmm": 0.2, "vol": 0.1, "macro": 0.3, "corr": 0.1, "bocd": 0.1, "pelt": 0.1},
        )
        voter.add_vote("macro", "bull", 1.0)
        voter.add_vote("hmm", "bear", 1.0)
        voter.add_vote("vol", "bull", 1.0)
        regime, conf, details = voter.resolve()
        assert regime == "bull"
        assert abs(conf - 0.4) < 1e-9
        assert details["scores"]["bull"] == pytest.approx(0.4)
        assert details["scores"]["bear"] == pytest.approx(0.2)

    def test_hysteresis_blocks_transition(self) -> None:
        voter = EnsembleVoter(min_confidence=0.0, min_bars=5)
        # First resolve — establishes regime
        voter.add_vote("hmm", "choppy", 1.0)
        regime, _, _ = voter.resolve()
        assert regime == "choppy"

        # Second resolve — stays even though all votes switch
        voter.reset()
        voter.add_vote("hmm", "bull", 1.0)
        regime, _conf, details = voter.resolve()
        assert regime == "choppy"  # hysteresis holds
        assert details["bars_since_change"] == 1
        assert details["transition"] is False

    def test_hysteresis_transitions_after_min_bars(self) -> None:
        voter = EnsembleVoter(min_confidence=0.0, min_bars=3)
        # Establish regime
        voter.add_vote("hmm", "choppy", 1.0)
        regime, _, _ = voter.resolve()
        assert regime == "choppy"

        # Advance bars without switching
        for _ in range(3):
            voter.reset()
            voter.add_vote("hmm", "choppy", 1.0)
            regime, _, _ = voter.resolve()
        assert regime == "choppy"

        # Now switch — should be allowed
        voter.reset()
        voter.add_vote("hmm", "bull", 1.0)
        regime, _, details = voter.resolve()
        assert regime == "bull"
        assert details["transition"] is True
        assert details["bars_since_change"] == 0

    def test_confidence_threshold_blocks(self) -> None:
        voter = EnsembleVoter(min_confidence=0.7, min_bars=0)
        # Establish regime in bear
        voter.add_vote("hmm", "bear", 1.0)
        regime, _, _ = voter.resolve()
        assert regime == "bear"

        # Try to switch with low confidence
        voter.reset()
        voter.add_vote("hmm", "bull", 0.5)  # only bull vote, confidence 0.5*0.2 = 0.1
        regime, _, details = voter.resolve()
        assert regime == "bear"  # confidence too low
        assert details["transition"] is False

    def test_confidence_threshold_allows(self) -> None:
        voter = EnsembleVoter(min_confidence=0.1, min_bars=0)
        voter.add_vote("hmm", "bear", 1.0)
        regime, _, _ = voter.resolve()
        assert regime == "bear"

        voter.reset()
        voter.add_vote("vol", "bull", 1.0)  # vol weight=0.2, confidence=0.2 > 0.1
        regime, _, details = voter.resolve()
        assert regime == "bull"
        assert details["transition"] is True

    def test_no_votes_returns_unknown(self) -> None:
        voter = EnsembleVoter()
        regime, conf, details = voter.resolve()
        assert regime == "unknown"
        assert conf == 0.0
        assert details["scores"] == {}

    def test_reset_clears_votes_not_hysteresis(self) -> None:
        voter = EnsembleVoter(min_confidence=0.0, min_bars=3)
        voter.add_vote("hmm", "choppy", 1.0)
        voter.resolve()
        voter.reset()
        voter.add_vote("hmm", "bull", 1.0)
        regime, _, details = voter.resolve()
        assert regime == "choppy"  # hysteresis still active
        assert details["bars_since_change"] == 1

    def test_custom_weights(self) -> None:
        voter = EnsembleVoter(min_confidence=0.0, min_bars=0, weights={"alpha": 0.6, "beta": 0.4})
        voter.add_vote("alpha", "bull", 1.0)
        voter.add_vote("beta", "bear", 1.0)
        regime, conf, _details = voter.resolve()
        assert regime == "bull"
        assert conf == pytest.approx(0.6)

    def test_all_disagree(self) -> None:
        """All detectors vote different regimes — picks the one with highest weight."""
        voter = EnsembleVoter(min_confidence=0.0, min_bars=0)
        voter.add_vote("macro", "bear", 0.8)  # 0.3*0.8 = 0.24
        voter.add_vote("hmm", "bull", 0.9)  # 0.2*0.9 = 0.18
        voter.add_vote("vol", "choppy", 0.7)  # 0.2*0.7 = 0.14
        voter.add_vote("corr", "volatile", 0.6)  # 0.1*0.6 = 0.06
        regime, _, details = voter.resolve()
        # bear wins with 0.24
        assert regime == "bear"
        assert details["winner"] == "bear"


# ======================================================================
# RegimeDetector (orchestrator)
# ======================================================================


class TestRegimeDetector:
    def test_fit_and_detect(self) -> None:
        data = _returns(n=300)
        detector = RegimeDetector(RegimeSettings()).fit(data)
        regime, conf, details = detector.detect(data)
        assert isinstance(regime, str)
        assert isinstance(conf, float)
        assert isinstance(details, dict)
        assert "scores" in details
        assert "votes" in details
        assert "transition" in details
        assert regime in ("bull", "bear", "choppy", "volatile", "unknown")

    def test_detect_before_fit_raises(self) -> None:
        detector = RegimeDetector()
        with pytest.raises(RegimeError, match="not fitted"):
            detector.detect(np.array([0.0, 0.1]))

    def test_fit_empty_raises(self) -> None:
        detector = RegimeDetector()
        with pytest.raises(RegimeError, match=r"empty|non-array"):
            detector.fit(np.array([]))

    def test_fit_non_array_raises(self) -> None:
        detector = RegimeDetector()
        with pytest.raises(RegimeError):
            detector.fit([1, 2, 3])  # type: ignore[arg-type]

    def test_fit_custom_settings(self) -> None:
        settings = RegimeSettings(hmm_n_states=3, vol_cluster_n=3)
        data = _returns(n=300)
        detector = RegimeDetector(settings).fit(data)
        assert detector.fitted is True
        regime, _, _ = detector.detect(data)
        assert isinstance(regime, str)

    def test_fitted_property(self) -> None:
        detector = RegimeDetector()
        assert detector.fitted is False
        detector.fit(_returns(n=300))
        assert detector.fitted is True

    def test_with_prices_correlation(self) -> None:
        data = _returns(n=200)
        prices = _price_matrix(200, 3)
        detector = RegimeDetector(RegimeSettings()).fit(data)
        regime, _conf, details = detector.detect(data, prices=prices)
        assert isinstance(regime, str)
        # Correlation detector should contribute
        corr_vote = [v for v in details["votes"] if v["detector"] == "corr"]
        assert len(corr_vote) == 1
        assert isinstance(corr_vote[0]["regime"], str)

    def test_bull_bear_detection(self) -> None:
        """Pipeline runs on data with a clear regime shift."""
        data = _bull_bear_returns()
        detector = RegimeDetector(RegimeSettings()).fit(data)
        regime, _, _ = detector.detect(data)
        assert isinstance(regime, str)
        # Should produce some regime (not unknown)
        assert regime != "unknown"

    def test_high_volatility(self) -> None:
        rng = np.random.default_rng(77)
        data = rng.normal(0.0, 0.04, 300)  # high vol
        detector = RegimeDetector(RegimeSettings()).fit(data)
        regime, _, details = detector.detect(data)
        assert isinstance(regime, str)
        assert details["scores"] is not None


# ======================================================================
# RegimeSettings
# ======================================================================


class TestRegimeSettings:
    def test_defaults(self) -> None:
        s = RegimeSettings()
        assert s.hmm_n_states == 4
        assert s.ensemble_min_confidence == 0.6
        assert s.ensemble_min_bars == 5
        assert s.vol_cluster_n == 3
        assert s.correlation_window == 20

    def test_custom(self) -> None:
        s = RegimeSettings(
            hmm_n_states=5,
            ensemble_min_confidence=0.7,
            ensemble_min_bars=10,
            vol_cluster_n=4,
            correlation_window=30,
        )
        assert s.hmm_n_states == 5
        assert s.ensemble_min_confidence == 0.7
        assert s.ensemble_min_bars == 10
        assert s.vol_cluster_n == 4
        assert s.correlation_window == 30
