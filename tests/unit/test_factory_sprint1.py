"""BL-708 — Unit tests for the Edge Research Factory Sprint 1 qualification.

The runner is intentionally narrow: every threshold and parameter is
frozen at sprint-time, so the tests focus on the *plumbing* (factor
construction, gauntlet pass-through, aggregation logic, report
serialisation) using synthetic data — never the live lake.

A few tests cross the live lake to assert the wiring against the
shipped data layout; they skip gracefully when the lake parquet files
are absent.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.run_factory_sprint1_qualification import (
    DEFAULT_HORIZON_DAILY,
    DSR_MIN,
    HAIRCUT_SHARPE_GATE,
    IC_BLOCK_T_THRESHOLD,
    IC_HAIRCUT_PCT,
    ICIR_THRESHOLD,
    VERDICT_GO,
    VERDICT_INSUFFICIENT,
    VERDICT_NO_GO,
    CandidateSpec,
    CandidateVerdict,
    PriceSeries,
    SlotResult,
    SprintReport,
    _aggregate_verdict,
    _evaluate_slot_single,
    _evaluate_slot_universe,
    _strategy_returns,
    crypto_carry_proxy_factor,
    render_markdown,
    reversion_factor,
    run_sprint,
    trend_cta_factor,
    value_composite_universe_factor,
)

# ---------------------------------------------------------------------------
# Fixtures: synthetic prices with planted signals
# ---------------------------------------------------------------------------


def _make_price_series(
    *,
    n: int = 1500,
    seed: int = 0,
    drift: float = 0.0004,
    vol: float = 0.01,
    asset: str = "SYN",
    timeframe: str = "1d",
    start: str = "2018-01-01",
) -> PriceSeries:
    """Synthetic GBM close series with optional drift."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, n)
    close = 100.0 * np.cumprod(1.0 + rets)
    idx = pd.date_range(start, periods=n, freq="1D", name="timestamp")
    return PriceSeries(
        asset=asset, timeframe=timeframe, close=pd.Series(close, index=idx, name=asset)
    )


def _make_trending_series(
    *, n: int = 1500, drift: float = 0.0008, seed: int = 1, asset: str = "TREND"
) -> PriceSeries:
    """Strong trend: drift dominates noise; close / SMA200 − 1 should be informative."""
    return _make_price_series(n=n, seed=seed, drift=drift, vol=0.005, asset=asset)


def _make_mean_reverting_series(*, n: int = 1500, seed: int = 2, asset: str = "REV") -> PriceSeries:
    """Ornstein-Uhlenbeck-ish: reverts to 100.  Negative z-score predicts + returns."""
    rng = np.random.default_rng(seed)
    close = np.full(n, 100.0)
    for i in range(1, n):
        close[i] = close[i - 1] + 0.05 * (100.0 - close[i - 1]) + rng.normal(0, 0.5)
    idx = pd.date_range("2018-01-01", periods=n, freq="1D", name="timestamp")
    return PriceSeries(asset=asset, timeframe="1d", close=pd.Series(close, index=idx, name=asset))


# ---------------------------------------------------------------------------
# Factor functions
# ---------------------------------------------------------------------------


def test_trend_cta_factor_basic_shape() -> None:
    ps = _make_trending_series(n=400, asset="T")
    factor, fwd = trend_cta_factor(ps, horizon=5)
    assert isinstance(factor, pd.Series)
    assert isinstance(fwd, pd.Series)
    # The factor's NaN-dropped index is a strict subset of the price index
    # (SMA200 warmup); the forward-return series has NaN at the tail (last
    # *horizon* bars).  The runner aligns via pd.concat(...).dropna().
    assert factor.dropna().index.isin(fwd.index).all()
    assert fwd.notna().sum() == 400 - 5
    # SMA200 with min_periods=200 produces 200 valid values out of 400,
    # spanning the rolling window's *last* index onwards.
    assert factor.dropna().size == 400 - (200 - 1)


def test_trend_cta_factor_positive_on_trending_market() -> None:
    """On a strongly trending series, the trend factor's mean should be > 0."""
    ps = _make_trending_series(n=600, drift=0.002, seed=7)
    factor, _ = trend_cta_factor(ps, horizon=5)
    assert factor.dropna().mean() > 0


def test_reversion_factor_basic_shape() -> None:
    ps = _make_mean_reverting_series(n=400, asset="R")
    factor, fwd = reversion_factor(ps, horizon=5)
    # Factor drops 20 bars (rolling warmup); forward return has NaN at tail.
    assert factor.dropna().index.isin(fwd.index).all()
    assert factor.dropna().size == 400 - (20 - 1)
    assert fwd.notna().sum() == 400 - 5


def test_reversion_factor_predicts_mean_reversion() -> None:
    """On a mean-reverting OU series, the -zscore factor should correlate
    positively with the forward return."""
    ps = _make_mean_reverting_series(n=1000, seed=42)
    factor, fwd = reversion_factor(ps, horizon=5)
    pair = pd.concat([factor, fwd], axis=1).dropna()
    rho = pair.corr().iloc[0, 1]
    assert rho > 0.05  # meaningful positive correlation


def test_crypto_carry_proxy_factor_basic_shape() -> None:
    ps = _make_price_series(n=300, asset="C")
    factor, _ = crypto_carry_proxy_factor(ps, horizon=5)
    assert factor.notna().sum() == 300 - 5  # 5-bar window


def test_value_composite_universe_factor_requires_two_assets() -> None:
    """Single-asset universe → None (rank undefined)."""
    ps = _make_price_series(n=200, asset="U")
    out = value_composite_universe_factor([ps], "1d", horizon=5)
    assert out is None


def test_value_composite_universe_factor_returns_pair() -> None:
    ps1 = _make_price_series(n=400, seed=11, asset="AAA")
    ps2 = _make_price_series(n=400, seed=22, asset="BBB")
    ps3 = _make_price_series(n=400, seed=33, asset="CCC")
    ps4 = _make_price_series(n=400, seed=44, asset="DDD")
    out = value_composite_universe_factor([ps1, ps2, ps3, ps4], "1d", horizon=5)
    assert out is not None
    factor, fwd = out
    assert isinstance(factor, pd.Series)
    assert isinstance(fwd, pd.Series)
    assert factor.index.equals(fwd.index)
    assert factor.dropna().between(0, 1).all()  # rank ∈ [0, 1]


# ---------------------------------------------------------------------------
# _strategy_returns
# ---------------------------------------------------------------------------


def test_strategy_returns_sign_application() -> None:
    f = pd.Series([1.0, -1.0, 0.5, -0.2], index=pd.date_range("2024-01-01", periods=4))
    r = pd.Series([0.01, -0.02, 0.005, 0.03], index=f.index)
    out = _strategy_returns(f, r)
    # sign(1)*0.01 = 0.01; sign(-1)*(-0.02) = 0.02; sign(0.5)*0.005 = 0.005; sign(-0.2)*0.03 = -0.03
    np.testing.assert_allclose(out.to_numpy(), np.array([0.01, 0.02, 0.005, -0.03]), atol=1e-12)


def test_strategy_returns_empty_on_no_overlap() -> None:
    f = pd.Series([1.0, 2.0], index=pd.date_range("2024-01-01", periods=2))
    r = pd.Series([], dtype=float)
    out = _strategy_returns(f, r)
    assert out.empty


# ---------------------------------------------------------------------------
# Single-slot evaluation
# ---------------------------------------------------------------------------


def _spec_with(family: str = "trend_cta", slots: tuple[tuple[str, str], ...] = ()) -> CandidateSpec:
    return CandidateSpec(
        family=family,
        label=family,
        description="test",
        registry_hypothesis_id=None,
        horizon_daily=DEFAULT_HORIZON_DAILY,
        horizon_hourly=24,
        factor_fn=trend_cta_factor,
        single_asset_slots=slots,
    )


def test_evaluate_slot_single_insufficient_data_on_tiny_series() -> None:
    ps = _make_trending_series(n=50, asset="X")
    spec = _spec_with(slots=(("X", "1d"),))
    res = _evaluate_slot_single(spec, "X", "1d", ps)
    assert res.status == "INSUFFICIENT_DATA"
    assert res.ic_passed is False


def test_evaluate_slot_single_ok_on_trending_series() -> None:
    ps = _make_trending_series(n=2000, drift=0.001, asset="TR")
    spec = CandidateSpec(
        family="trend_cta",
        label="trend",
        description="t",
        registry_hypothesis_id=None,
        horizon_daily=5,
        horizon_hourly=24,
        factor_fn=trend_cta_factor,
        single_asset_slots=(("TR", "1d"),),
    )
    res = _evaluate_slot_single(spec, "TR", "1d", ps)
    assert res.status == "OK"
    assert res.n_pairs > 0
    assert math.isfinite(res.ic_mean)
    # Either IC passed (strong signal) or the haircut SR is finite.
    assert math.isfinite(res.haircut_sharpe)


# ---------------------------------------------------------------------------
# Universe slot evaluation
# ---------------------------------------------------------------------------


def test_evaluate_slot_universe_insufficient_when_no_overlap() -> None:
    spec = CandidateSpec(
        family="value_composite",
        label="vc",
        description="v",
        registry_hypothesis_id=None,
        horizon_daily=5,
        horizon_hourly=24,
        factor_fn=None,
        universe_assets=("AAA", "BBB"),
    )
    ps1 = _make_price_series(n=200, seed=11, asset="AAA")
    res = _evaluate_slot_universe(spec, "1d", [ps1])
    assert res.status == "INSUFFICIENT_DATA"


def test_evaluate_slot_universe_ok_on_synthetic_universe() -> None:
    ps1 = _make_price_series(n=600, seed=11, asset="AAA")
    ps2 = _make_price_series(n=600, seed=22, asset="BBB")
    ps3 = _make_price_series(n=600, seed=33, asset="CCC")
    ps4 = _make_price_series(n=600, seed=44, asset="DDD")
    spec = CandidateSpec(
        family="value_composite",
        label="vc",
        description="v",
        registry_hypothesis_id=None,
        horizon_daily=5,
        horizon_hourly=24,
        factor_fn=None,
        universe_assets=("AAA", "BBB", "CCC", "DDD"),
    )
    res = _evaluate_slot_universe(spec, "1d", [ps1, ps2, ps3, ps4])
    assert res.status == "OK"
    assert res.n_pairs > 100
    # The 1/close rank is a noise factor on synthetic GBM; we only assert
    # finite metrics, not direction (the proxy is intentionally weak).
    assert math.isfinite(res.ic_mean)


# ---------------------------------------------------------------------------
# Verdict aggregation
# ---------------------------------------------------------------------------


def _slot(
    family: str,
    asset: str,
    timeframe: str,
    *,
    status: str = "OK",
    ic_passed: bool = False,
    haircut_sharpe: float = 0.0,
    dsr: float | None = 0.3,
    psr: float | None = 0.5,
) -> SlotResult:
    return SlotResult(
        family=family,
        label=family,
        asset=asset,
        timeframe=timeframe,
        n_bars=500,
        n_pairs=400,
        ic_passed=ic_passed,
        ic_mean=0.05,
        ic_std=0.1,
        icir_raw=0.5,
        icir_haircut=0.4,
        ic_t_block=3.0,
        observed_sharpe=0.5,
        haircut_sharpe=haircut_sharpe,
        psr=psr,
        dsr=dsr,
        status=status,
    )


def test_aggregate_verdict_go_when_all_gates_pass() -> None:
    spec = _spec_with(slots=(("A", "1d"), ("B", "1d"), ("C", "1d")))
    slots = [
        _slot("trend_cta", "A", "1d", ic_passed=True, haircut_sharpe=0.3, dsr=0.6),
        _slot("trend_cta", "B", "1d", ic_passed=True, haircut_sharpe=0.2, dsr=0.7),
        _slot("trend_cta", "C", "1d", ic_passed=True, haircut_sharpe=0.1, dsr=0.5),
    ]
    v = _aggregate_verdict(spec, slots)
    assert v.verdict == VERDICT_GO
    assert v.n_slots_passing_ic == 3
    assert v.reasons == []


def test_aggregate_verdict_no_go_on_kill_criterion() -> None:
    """Fewer than KILL_MIN_PASSING_SLOTS IC-pass slots → NO-GO."""
    spec = _spec_with(slots=(("A", "1d"), ("B", "1d")))
    slots = [
        _slot("trend_cta", "A", "1d", ic_passed=True, haircut_sharpe=0.5, dsr=0.6),
        _slot("trend_cta", "B", "1d", ic_passed=False, haircut_sharpe=0.5, dsr=0.6),
    ]
    v = _aggregate_verdict(spec, slots)
    assert v.verdict == VERDICT_NO_GO
    assert any("IC screen" in r for r in v.reasons)


def test_aggregate_verdict_no_go_on_negative_median_haircut() -> None:
    spec = _spec_with(slots=(("A", "1d"), ("B", "1d"), ("C", "1d")))
    slots = [
        _slot("trend_cta", "A", "1d", ic_passed=True, haircut_sharpe=0.5, dsr=0.6),
        _slot("trend_cta", "B", "1d", ic_passed=True, haircut_sharpe=-0.5, dsr=0.6),
        _slot("trend_cta", "C", "1d", ic_passed=True, haircut_sharpe=-0.5, dsr=0.6),
    ]
    v = _aggregate_verdict(spec, slots)
    assert v.verdict == VERDICT_NO_GO
    assert any("haircut Sharpe" in r for r in v.reasons)


def test_aggregate_verdict_no_go_on_low_median_dsr() -> None:
    spec = _spec_with(slots=(("A", "1d"), ("B", "1d"), ("C", "1d")))
    slots = [
        _slot("trend_cta", "A", "1d", ic_passed=True, haircut_sharpe=0.5, dsr=0.3),
        _slot("trend_cta", "B", "1d", ic_passed=True, haircut_sharpe=0.5, dsr=0.4),
        _slot("trend_cta", "C", "1d", ic_passed=True, haircut_sharpe=0.5, dsr=0.4),
    ]
    v = _aggregate_verdict(spec, slots)
    assert v.verdict == VERDICT_NO_GO
    assert any("DSR" in r for r in v.reasons)


def test_aggregate_verdict_insufficient_data() -> None:
    spec = _spec_with(slots=(("A", "1d"),))
    slots = [_slot("trend_cta", "A", "1d", status="INSUFFICIENT_DATA")]
    v = _aggregate_verdict(spec, slots)
    assert v.verdict == VERDICT_INSUFFICIENT


# ---------------------------------------------------------------------------
# run_sprint integration (uses real lake if available, else synthetic)
# ---------------------------------------------------------------------------


def test_run_sprint_against_synthetic_lake(tmp_path: Path) -> None:
    """End-to-end against a tiny synthetic lake (no parquet needed).

    Writes a handful of synthetic 1d parquet files for the default
    candidate slots, then runs the gauntlet and asserts:
      - 4 candidate verdicts returned
      - kill-criterion signal is computed
      - JSON / MD reports serialize cleanly
    """
    import polars as pl

    lake = tmp_path / "lake"
    lake.mkdir()

    # Trend CTA: write 5 of the 6 default slots
    assets_daily = [
        ("ES", 0.0004, 0.01, 1),
        ("NQ", 0.0005, 0.012, 2),
        ("CL", 0.0002, 0.013, 3),
        ("GC", 0.0001, 0.009, 4),
        ("BTCUSDT", 0.001, 0.04, 5),
        ("ETHUSDT", 0.0012, 0.045, 6),
    ]
    for asset, drift, vol, seed in assets_daily:
        rng = np.random.default_rng(seed)
        n = 1500
        rets = rng.normal(drift, vol, n)
        close = 100.0 * np.cumprod(1.0 + rets)
        ts = pd.date_range("2018-01-01", periods=n, freq="1D")
        df = pd.DataFrame({"timestamp": ts, "close": close})
        pl.from_pandas(df).write_parquet(lake / f"{asset}_1d.parquet")

    # Reversion: write ES/BTCUSDT/EURUSD 1d (other defaults skip gracefully)
    for asset, seed in [("ES", 11), ("BTCUSDT", 12), ("EURUSD", 13)]:
        rng = np.random.default_rng(seed)
        n = 1500
        close = np.full(n, 100.0)
        for i in range(1, n):
            close[i] = close[i - 1] + 0.05 * (100.0 - close[i - 1]) + rng.normal(0, 0.5)
        ts = pd.date_range("2018-01-01", periods=n, freq="1D")
        df = pd.DataFrame({"timestamp": ts, "close": close})
        pl.from_pandas(df).write_parquet(lake / f"{asset}_1d.parquet")

    # Crypto carry: BTCUSDT/ETHUSDT/SOLUSDT 1d
    for asset, seed in [("BTCUSDT", 21), ("ETHUSDT", 22), ("SOLUSDT", 23)]:
        rng = np.random.default_rng(seed)
        n = 1500
        rets = rng.normal(0.001, 0.04, n)
        close = 100.0 * np.cumprod(1.0 + rets)
        ts = pd.date_range("2018-01-01", periods=n, freq="1D")
        df = pd.DataFrame({"timestamp": ts, "close": close})
        pl.from_pandas(df).write_parquet(lake / f"{asset}_1d.parquet")

    # Value composite: AAPL/MSFT/SPY/QQQ/IWM/DIA/XLK/XLF
    for asset, seed in [
        ("AAPL", 31),
        ("MSFT", 32),
        ("SPY", 33),
        ("QQQ", 34),
        ("IWM", 35),
        ("DIA", 36),
        ("XLK", 37),
        ("XLF", 38),
    ]:
        rng = np.random.default_rng(seed)
        n = 1500
        rets = rng.normal(0.0004, 0.015, n)
        close = 100.0 * np.cumprod(1.0 + rets)
        ts = pd.date_range("2018-01-01", periods=n, freq="1D")
        df = pd.DataFrame({"timestamp": ts, "close": close})
        pl.from_pandas(df).write_parquet(lake / f"{asset}_1d.parquet")

    report = run_sprint(lake_root=lake)

    # 4 candidates, 1 verdict each.
    assert len(report.candidates) == 4
    for c in report.candidates:
        assert c.family in {"trend_cta", "value_composite", "reversion", "crypto_carry"}

    # Kill criterion signal is a bool.
    assert isinstance(report.kill_criterion_triggered, bool)
    assert report.total_passing_ic >= 0

    # Slot count > 0 because we wrote synthetic files for the assets.
    assert len(report.slots) > 0
    # And every slot has the candidate family populated.
    for s in report.slots:
        assert s.family in {"trend_cta", "value_composite", "reversion", "crypto_carry"}


def test_run_sprint_handles_missing_lake_files(tmp_path: Path) -> None:
    """Empty lake → at least one slot per candidate with LOAD_ERROR or INSUFFICIENT_DATA."""
    lake = tmp_path / "empty"
    lake.mkdir()
    report = run_sprint(lake_root=lake)
    assert len(report.candidates) == 4
    # With no data, every verdict should be either INSUFFICIENT_DATA or NO_GO.
    for c in report.candidates:
        assert c.verdict in {VERDICT_NO_GO, VERDICT_INSUFFICIENT}


# ---------------------------------------------------------------------------
# Report serialization
# ---------------------------------------------------------------------------


def _sample_report() -> SprintReport:
    slots = [
        SlotResult(
            family="trend_cta",
            label="Trend CTA",
            asset="ES",
            timeframe="1d",
            n_bars=1500,
            n_pairs=1200,
            ic_passed=True,
            ic_mean=0.05,
            ic_std=0.10,
            icir_raw=0.50,
            icir_haircut=0.35,
            ic_t_block=3.5,
            observed_sharpe=0.40,
            haircut_sharpe=0.20,
            psr=0.65,
            dsr=0.55,
            status="OK",
        ),
        SlotResult(
            family="reversion",
            label="Reversion",
            asset="BTCUSDT",
            timeframe="1d",
            n_bars=1500,
            n_pairs=1200,
            ic_passed=False,
            ic_mean=-0.01,
            ic_std=0.12,
            icir_raw=-0.08,
            icir_haircut=-0.06,
            ic_t_block=-1.0,
            observed_sharpe=-0.10,
            haircut_sharpe=-0.20,
            psr=0.20,
            dsr=0.15,
            status="OK",
        ),
    ]
    candidates = [
        CandidateVerdict(
            family="trend_cta",
            label="Trend CTA",
            description="trend factor",
            registry_hypothesis_id=None,
            verdict=VERDICT_GO,
            n_slots_total=1,
            n_slots_ok=1,
            n_slots_passing_ic=1,
            median_haircut_sharpe=0.20,
            median_dsr=0.55,
            median_psr=0.65,
            reasons=[],
            notes="",
        ),
        CandidateVerdict(
            family="reversion",
            label="Reversion",
            description="mean-reversion",
            registry_hypothesis_id=None,
            verdict=VERDICT_NO_GO,
            n_slots_total=1,
            n_slots_ok=1,
            n_slots_passing_ic=0,
            median_haircut_sharpe=-0.20,
            median_dsr=0.15,
            median_psr=0.20,
            reasons=["only 0 slots pass the IC screen"],
            notes="",
        ),
    ]
    return SprintReport(
        generated_at="2026-09-03T00:00:00+00:00",
        candidates=candidates,
        slots=slots,
        kill_criterion_triggered=False,
        total_passing_ic=1,
        thresholds={
            "icir_threshold": ICIR_THRESHOLD,
            "ic_block_t_threshold": IC_BLOCK_T_THRESHOLD,
            "ic_haircut_pct": IC_HAIRCUT_PCT,
            "haircut_sharpe_min": HAIRCUT_SHARPE_GATE,
            "dsr_min": DSR_MIN,
            "psr_min": 0.5,
        },
    )


def test_render_markdown_contains_top_line_verdicts() -> None:
    md = render_markdown(_sample_report())
    assert "# BL-708" in md
    assert "Trend CTA" in md
    assert "Reversion" in md
    assert "GO" in md
    assert "NO-GO" in md


def test_render_markdown_contains_threshold_table() -> None:
    md = render_markdown(_sample_report())
    assert "icir_threshold" in md
    assert f"{ICIR_THRESHOLD}" in md


def test_render_markdown_kill_criterion_section_appears_when_triggered() -> None:
    report = _sample_report()
    report.kill_criterion_triggered = True
    md = render_markdown(report)
    assert "KILL CRITERION TRIGGERED" in md


def test_render_markdown_includes_per_candidate_slot_table() -> None:
    md = render_markdown(_sample_report())
    # Slot-table headers are present for each candidate.
    assert "asset" in md
    assert "IC" in md
    assert "DSR" in md


def test_sprint_report_as_dict_round_trips_json() -> None:
    payload = _sample_report().as_dict()
    blob = json.dumps(payload, default=str)
    parsed = json.loads(blob)
    assert "metadata" in parsed
    assert "candidates" in parsed
    assert "slots" in parsed
    assert "kill_criterion" in parsed
    assert parsed["kill_criterion"]["total_passing_ic"] == 1
    assert parsed["kill_criterion"]["triggered"] is False


def test_sprint_report_thresholds_are_frozen() -> None:
    """Sanity: the frozen thresholds make it into the report payload."""
    rep = _sample_report()
    payload = rep.as_dict()
    th = payload["metadata"]["thresholds"]
    assert th["icir_threshold"] == pytest.approx(ICIR_THRESHOLD)
    assert th["ic_block_t_threshold"] == pytest.approx(IC_BLOCK_T_THRESHOLD)
    assert th["ic_haircut_pct"] == pytest.approx(IC_HAIRCUT_PCT)


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def test_cli_help_runs(capsys: pytest.CaptureFixture[str]) -> None:
    """The runner must accept --help without crashing (CLI smoke)."""
    from scripts.run_factory_sprint1_qualification import _parse_args

    with pytest.raises(SystemExit) as exc:
        _parse_args(["--help"])
    assert exc.value.code == 0


def test_cli_writes_reports(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """End-to-end CLI: write a synthetic lake, run main(), check outputs."""
    import polars as pl

    lake = tmp_path / "lake"
    lake.mkdir()
    rng = np.random.default_rng(0)
    n = 800
    rets = rng.normal(0.0005, 0.012, n)
    close = 100.0 * np.cumprod(1.0 + rets)
    ts = pd.date_range("2018-01-01", periods=n, freq="1D")
    df = pd.DataFrame({"timestamp": ts, "close": close})
    pl.from_pandas(df).write_parquet(lake / "ES_1d.parquet")
    pl.from_pandas(df).write_parquet(lake / "BTCUSDT_1d.parquet")
    pl.from_pandas(df).write_parquet(lake / "ETHUSDT_1d.parquet")
    pl.from_pandas(df).write_parquet(lake / "EURUSD_1d.parquet")
    pl.from_pandas(df).write_parquet(lake / "CL_1d.parquet")
    pl.from_pandas(df).write_parquet(lake / "GC_1d.parquet")
    pl.from_pandas(df).write_parquet(lake / "NQ_1d.parquet")
    pl.from_pandas(df).write_parquet(lake / "SOLUSDT_1d.parquet")
    pl.from_pandas(df).write_parquet(lake / "AAPL_1d.parquet")
    pl.from_pandas(df).write_parquet(lake / "MSFT_1d.parquet")
    pl.from_pandas(df).write_parquet(lake / "SPY_1d.parquet")
    pl.from_pandas(df).write_parquet(lake / "QQQ_1d.parquet")
    pl.from_pandas(df).write_parquet(lake / "IWM_1d.parquet")
    pl.from_pandas(df).write_parquet(lake / "DIA_1d.parquet")
    pl.from_pandas(df).write_parquet(lake / "XLK_1d.parquet")
    pl.from_pandas(df).write_parquet(lake / "XLF_1d.parquet")

    out = tmp_path / "reports"
    from scripts.run_factory_sprint1_qualification import main

    rc = main(["--lake-root", str(lake), "--out-dir", str(out)])
    assert rc == 0
    assert (out / "sprint-1.md").exists()
    assert (out / "sprint-1.json").exists()
    body = (out / "sprint-1.md").read_text(encoding="utf-8")
    assert "BL-708" in body
    parsed = json.loads((out / "sprint-1.json").read_text(encoding="utf-8"))
    assert "candidates" in parsed
    assert "slots" in parsed


# ---------------------------------------------------------------------------
# Live lake (optional — skips if data is absent)
# ---------------------------------------------------------------------------


LIVE_LAKE = Path("/home/alin/_repos/oracle-trading/data/lake/curated")


@pytest.mark.skipif(not LIVE_LAKE.exists(), reason="shipped lake parquet not present")
def test_live_lake_sprint_end_to_end() -> None:
    """Real-data smoke: the runner must complete without raising against the shipped lake."""
    report = run_sprint(lake_root=LIVE_LAKE)
    assert len(report.candidates) == 4
    for c in report.candidates:
        # Every verdict is one of the three allowed codes.
        assert c.verdict in {VERDICT_GO, VERDICT_NO_GO, VERDICT_INSUFFICIENT}
    # Generated timestamp parses as ISO-8601.
    datetime.fromisoformat(report.generated_at)
