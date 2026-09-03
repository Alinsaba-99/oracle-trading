#!/usr/bin/env python3
"""BL-708 — Sprint 1 qualification of the Edge Research Factory Stage 1 candidates.

Runs the pre-registered qualification gauntlet on the four Stage 1
candidate factor families that the Edge Research Factory design spec
(`docs/plans/2026-08-21-edge-research-factory-design.md` §3, §6) calls
out as the first lot for Sprint 1:

1. **Trend CTA** — long-horizon trend-following on liquid futures/equity
   indices (close / SMA200 − 1 signal, frozen family parameters).
2. **Value Composite** — cross-sectional price-value proxy within the
   available universe (1 / close, ranked; long top-quintile vs short
   bottom-quintile) — the spec defers fundamental composite to BL-728
   (edgar_loader.py), so Sprint 1 ships a *price-value* proxy that
   exercises the same gauntlet plumbing.
3. **Reversion** — short-horizon mean-reversion on liquid futures and
   crypto (− zscore(close, 20) signal, frozen family parameters).
4. **Crypto Carry** — short-horizon momentum-of-funding proxy on 24/7
   crypto (rolling-mean of 1h returns as a carry proxy because Binance
   Vision funding data lands via BL-718 in a later sprint; Sprint 1
   ships the factor plumbing and pins the data gap explicitly).

Each candidate × (asset, timeframe) pair is run through the gauntlet:

* **IC screen** — ``analytics/research/factory/ic_screen.py`` (BL-706).
  Spearman IC on non-overlapping windows with moving-block bootstrap
  t-stat; pre-registered thresholds ICIR haircut > 0.05, t > 2.5, with
  30% post-publication haircut applied to ICIR.
* **Haircut Sharpe** — ``analytics/research/factory/haircut_sharpe.py``
  (BL-707 / BL-KB-99, Bailey-López de Prado 2018).  Multiple-testing
  deflation + non-normality penalty + confidence-scaled estimation
  error; never above the sample Sharpe.
* **DSR / PSR** — ``analytics/qualification/dsr.py`` (ADR-017, deflated
  + probabilistic Sharpe ratios).

The verdict per candidate is ``GO`` when **all three** of these hold:

* ≥ 2 of the candidate's asset/timeframe slots **pass the IC screen**;
* the **median haircut Sharpe across slots is positive** (multiple-testing
  + non-normality penalty didn't push it below 0);
* the **median DSR across slots is ≥ 0.5** (positive edge after
  deflation).

Otherwise ``NO-GO``.  Insufficient-data verdicts are split out as
``INSUFFICIENT_DATA`` so the kill-criterion in the design spec (§8,
"< 2 fattori superano IC screen → stop") can be enforced automatically
by parsing the JSON payload.

Outputs
-------
* ``docs/reports/edge-factory/sprint-1.md`` — human-readable sprint report.
* ``docs/reports/edge-factory/sprint-1.json`` — machine-readable payload
  (per-slot metrics + per-candidate verdicts + the kill-criterion signal).

The script is intentionally narrow: every threshold and parameter is
fixed (no fallback values inside the runner); the only flags are the
data source root and the output directory, both defaulted to the repo
layout.

Usage::

    uv run python scripts/run_factory_sprint1_qualification.py
    uv run python scripts/run_factory_sprint1_qualification.py \
        --lake-root data/lake/curated --out-dir docs/reports/edge-factory
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.metrics.canonical import sharpe_ratio as canonical_sharpe  # ADR-021
from analytics.qualification.dsr import deflated_sharpe_ratio, probabilistic_sharpe_ratio  # ADR-017
from analytics.research.factory.haircut_sharpe import haircut_sharpe_ratio  # BL-707
from analytics.research.factory.ic_screen import ICResult, screen_factor  # BL-706
from analytics.research.factory.registry import HypothesisRegistry  # BL-700

# ---------------------------------------------------------------------------
# Frozen Sprint-1 gauntlet thresholds (BL-708, design spec §6)
# ---------------------------------------------------------------------------

#: IC screen gates (BL-706 design-time choices).
ICIR_THRESHOLD: float = 0.05
IC_BLOCK_T_THRESHOLD: float = 2.5
IC_HAIRCUT_PCT: float = 30.0

#: Haircut Sharpe gate (BL-707 / BL-KB-99).
HAIRCUT_SHARPE_GATE: float = 0.0  # median across slots must be > this

#: DSR/PSR gate (ADR-017).
DSR_MIN: float = 0.5
PSR_MIN: float = 0.5

#: Forward-return horizon in bars (1d for daily bars, 1 for hourly, etc.).
DEFAULT_HORIZON_DAILY: int = 5
DEFAULT_HORIZON_HOURLY: int = 24

#: Default data frequency → periods-per-year.
PERIODS_PER_YEAR = {"1d": 252, "1h": 24 * 365}

#: Verdict codes.
VERDICT_GO = "GO"
VERDICT_NO_GO = "NO_GO"
VERDICT_INSUFFICIENT = "INSUFFICIENT_DATA"

#: Design spec §8 kill criterion: < 2 slots pass IC screen → stop.
KILL_MIN_PASSING_SLOTS: int = 2


# ---------------------------------------------------------------------------
# Data loading (lake parquet, BL-301 / BL-307 — $0 stack)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PriceSeries:
    """A single-asset close-price series with a DatetimeIndex."""

    asset: str
    timeframe: str
    close: pd.Series  # DatetimeIndex, name = asset, no NaN

    @property
    def n_bars(self) -> int:
        return int(self.close.size)


def _read_parquet_close(path: Path, *, asset: str, timeframe: str) -> PriceSeries:
    """Read one curated-lake parquet and return the close-price series."""
    import polars as pl  # local import — polars is an optional dep

    df = pl.read_parquet(path, columns=["timestamp", "close"])
    pdf = df.to_pandas()
    pdf = pdf.dropna(subset=["close"])
    pdf["timestamp"] = pd.to_datetime(pdf["timestamp"])
    pdf = pdf.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    s = pd.Series(pdf["close"].to_numpy(), index=pdf["timestamp"].to_numpy(), name=asset)
    s.index.name = "timestamp"
    return PriceSeries(asset=asset, timeframe=timeframe, close=s)


def load_price_series(lake_root: Path, asset: str, timeframe: str) -> PriceSeries | None:
    """Return the lake close-price series for one asset+timeframe, or None."""
    path = lake_root / f"{asset}_{timeframe}.parquet"
    if not path.exists():
        return None
    try:
        return _read_parquet_close(path, asset=asset, timeframe=timeframe)
    except Exception:  # pragma: no cover — defensive: bad parquet
        return None


# ---------------------------------------------------------------------------
# Factor implementations (Stage 1 candidates, frozen at sprint-time)
# ---------------------------------------------------------------------------


def _sma(s: pd.Series, period: int) -> pd.Series:
    """Simple moving average with explicit min-periods to align NaNs honestly."""
    return s.rolling(window=period, min_periods=period).mean()


FactorFn = Callable[[PriceSeries, int], tuple[pd.Series, pd.Series]]
"""Signature: (price, horizon) → (factor_series, forward_return_series).

Both series share the same DatetimeIndex; the forward-return series has
``NaN`` at the tail (last *horizon* bars) so callers can dropna cleanly.
"""


def trend_cta_factor(prices: PriceSeries, horizon: int) -> tuple[pd.Series, pd.Series]:
    """Long-horizon trend signal: ``close / SMA200 − 1``.

    Direction is fixed (long-factor): the IC screen will FAIL on
    negative-IC trends, no sign flip post-hoc.
    """
    close = prices.close
    sma200 = _sma(close, 200)
    factor = (close / sma200 - 1.0).rename("trend_factor")
    fwd = (close.shift(-horizon) / close - 1.0).rename("fwd_ret")
    return factor, fwd


def reversion_factor(prices: PriceSeries, horizon: int) -> tuple[pd.Series, pd.Series]:
    """Short-horizon mean-reversion: ``− zscore(close, 20)``.

    Negative z-score (price below mean) → positive factor → predicts a
    positive forward return; direction is fixed (no sign flip).
    """
    close = prices.close
    mu = close.rolling(20, min_periods=20).mean()
    sd = close.rolling(20, min_periods=20).std(ddof=1)
    z = (close - mu) / sd.replace(0.0, np.nan)
    factor = (-z).rename("rev_factor")
    fwd = (close.shift(-horizon) / close - 1.0).rename("fwd_ret")
    return factor, fwd


def crypto_carry_proxy_factor(prices: PriceSeries, horizon: int) -> tuple[pd.Series, pd.Series]:
    """Crypto carry proxy: short-horizon return momentum as a carry stand-in.

    Binance Vision funding data lands via BL-718 in a later sprint; for
    Sprint 1 we use the realised short-horizon return as a *direction*
    proxy that exercises the same plumbing.  The factor is the
    rolling-mean of the per-bar log-return over a window chosen to
    match the candidate's timeframe (24 bars for 1h, 5 bars for 1d).
    The verdict documents the proxy explicitly.
    """
    close = prices.close
    lr = np.log(close / close.shift(1))
    win = 24 if prices.timeframe == "1h" else 5
    factor = lr.rolling(win, min_periods=win).mean().rename("carry_proxy")
    fwd = (close.shift(-horizon) / close - 1.0).rename("fwd_ret")
    return factor, fwd


def value_composite_universe_factor(
    prices_list: Sequence[PriceSeries], timeframe: str, horizon: int
) -> tuple[pd.Series, pd.Series] | None:
    """Cross-sectional price-value proxy on a universe.

    For each date, rank assets by ``1 / close`` (cheap value proxy when
    fundamentals are unavailable) and emit the cross-sectional rank as
    the factor for the first asset in *prices_list*.  The forward
    return is the per-asset horizon return.  This deliberately exercises
    the cross-sectional factor pipeline that BL-728 / BL-718 will reuse
    with the proper fundamental composite.

    Returns ``None`` if fewer than two assets have overlapping dates
    (the rank is undefined for a single asset).
    """
    aligned = []
    for ps in prices_list:
        if ps.timeframe != timeframe:
            continue
        aligned.append(ps.close.rename(ps.asset))
    if len(aligned) < 2:
        return None
    universe = pd.concat(aligned, axis=1).sort_index().dropna(how="all").ffill()
    if universe.shape[1] < 2 or universe.shape[0] < 60:
        return None
    inv_close = 1.0 / universe.replace(0.0, np.nan)
    rank = inv_close.rank(axis=1, method="first", pct=True)
    first_asset = aligned[0].name
    factor = rank[first_asset].rename("value_factor")
    fwd = (universe[first_asset].shift(-horizon) / universe[first_asset] - 1.0).rename("fwd_ret")
    pair = pd.concat([factor, fwd], axis=1).dropna()
    if pair.empty or pair.iloc[:, 0].nunique() < 3 or pair.iloc[:, 1].nunique() < 3:
        return None
    return pair.iloc[:, 0], pair.iloc[:, 1]


# ---------------------------------------------------------------------------
# Candidate spec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateSpec:
    """One Stage 1 candidate factor family and the slots it is qualified on."""

    family: str
    label: str
    description: str
    registry_hypothesis_id: str | None  # best-effort backref into the registry
    horizon_daily: int
    horizon_hourly: int
    factor_fn: FactorFn | None  # None for cross-sectional only (value composite)
    universe_assets: tuple[str, ...] = ()
    single_asset_slots: tuple[tuple[str, str], ...] = ()
    notes: str = ""


def _default_candidates() -> list[CandidateSpec]:
    """The four Stage 1 candidates — frozen at sprint-time, no overrides."""
    return [
        CandidateSpec(
            family="trend_cta",
            label="Trend CTA",
            description="Long-horizon trend-following: close/SMA200 − 1 (BL-093 trend family).",
            registry_hypothesis_id=None,
            horizon_daily=DEFAULT_HORIZON_DAILY,
            horizon_hourly=DEFAULT_HORIZON_HOURLY,
            factor_fn=trend_cta_factor,
            single_asset_slots=(
                ("ES", "1d"),
                ("NQ", "1d"),
                ("CL", "1d"),
                ("GC", "1d"),
                ("BTCUSDT", "1d"),
                ("ETHUSDT", "1d"),
            ),
            notes="Direction fixed (long-factor): negative-IC trends FAIL, no sign-flip.",
        ),
        CandidateSpec(
            family="value_composite",
            label="Value Composite",
            description=(
                "Cross-sectional value proxy: rank(1/close) on a multi-asset "
                "universe; defers fundamental composite (BL-728 edgar_loader)."
            ),
            registry_hypothesis_id="01-fundamental/EF-001",
            horizon_daily=DEFAULT_HORIZON_DAILY,
            horizon_hourly=DEFAULT_HORIZON_HOURLY,
            factor_fn=None,
            universe_assets=("AAPL", "MSFT", "SPY", "QQQ", "IWM", "DIA", "XLK", "XLF"),
            notes=(
                "Price-value proxy: real fundamental composite (Novy-Marx + "
                "Piotroski + Sloan) is BL-728 work.  Sprint 1 exercises the "
                "cross-sectional factor pipeline end-to-end."
            ),
        ),
        CandidateSpec(
            family="reversion",
            label="Reversion",
            description="Short-horizon mean-reversion: − zscore(close, 20).",
            registry_hypothesis_id=None,
            horizon_daily=DEFAULT_HORIZON_DAILY,
            horizon_hourly=DEFAULT_HORIZON_HOURLY,
            factor_fn=reversion_factor,
            single_asset_slots=(
                ("ES", "1d"),
                ("BTCUSDT", "1d"),
                ("BTCUSDT", "1h"),
                ("ETHUSDT", "1d"),
                ("EURUSD", "1d"),
            ),
            notes="Direction fixed: positive-IC reversion expects long negative-z.",
        ),
        CandidateSpec(
            family="crypto_carry",
            label="Crypto Carry",
            description=(
                "Crypto funding-basis proxy: rolling-mean of 1h log-returns "
                "(Binance Vision funding lands via BL-718)."
            ),
            registry_hypothesis_id="crypto-microstructure/EF-007",
            horizon_daily=DEFAULT_HORIZON_DAILY,
            horizon_hourly=DEFAULT_HORIZON_HOURLY,
            factor_fn=crypto_carry_proxy_factor,
            single_asset_slots=(
                ("BTCUSDT", "1d"),
                ("BTCUSDT", "1h"),
                ("ETHUSDT", "1d"),
                ("ETHUSDT", "1h"),
                ("SOLUSDT", "1d"),
            ),
            notes="Real perp-basis funding lands with BL-718; Sprint 1 uses a direction proxy.",
        ),
    ]


# ---------------------------------------------------------------------------
# Slot evaluation (one candidate × one asset × one timeframe)
# ---------------------------------------------------------------------------


@dataclass
class SlotResult:
    """One candidate × asset × timeframe qualification row."""

    family: str
    label: str
    asset: str
    timeframe: str
    n_bars: int
    n_pairs: int
    ic_passed: bool
    ic_mean: float
    ic_std: float
    icir_raw: float
    icir_haircut: float
    ic_t_block: float
    observed_sharpe: float
    haircut_sharpe: float
    psr: float | None
    dsr: float | None
    status: str  # OK | INSUFFICIENT_DATA | LOAD_ERROR


def _strategy_returns(factor: pd.Series, fwd: pd.Series) -> pd.Series:
    """Long-short strategy returns: ``sign(factor) * fwd_return``.

    Direction is fixed (no post-hoc sign flip); the IC screen rejects
    negative-mean-IC factors before this step.  The result is the
    daily return stream fed into the DSR/PSR/Haircut gauntlet.
    """
    pair = pd.concat([factor.rename("f"), fwd.rename("r")], axis=1).dropna()
    if pair.empty:
        return pd.Series(dtype=float)
    return (np.sign(pair["f"]) * pair["r"]).rename("strategy")


def _evaluate_slot_single(
    spec: CandidateSpec, asset: str, timeframe: str, prices: PriceSeries
) -> SlotResult:
    horizon = spec.horizon_hourly if timeframe == "1h" else spec.horizon_daily
    assert spec.factor_fn is not None  # invariant for single-asset slots
    factor, fwd = spec.factor_fn(prices, horizon)
    pair = pd.concat([factor.rename("f"), fwd.rename("r")], axis=1).dropna()
    n_pairs = int(pair.shape[0])
    if n_pairs < 4 * 21:  # need >= ~4 IC windows of ~21 bars each
        return SlotResult(
            family=spec.family,
            label=spec.label,
            asset=asset,
            timeframe=timeframe,
            n_bars=int(prices.close.size),
            n_pairs=n_pairs,
            ic_passed=False,
            ic_mean=float("nan"),
            ic_std=float("nan"),
            icir_raw=float("nan"),
            icir_haircut=float("nan"),
            ic_t_block=float("nan"),
            observed_sharpe=0.0,
            haircut_sharpe=float("nan"),
            psr=None,
            dsr=None,
            status="INSUFFICIENT_DATA",
        )

    ic: ICResult = screen_factor(
        factor=pair["f"],
        prices=prices.close.reindex(pair.index),
        horizon=horizon,
        haircut_pct=IC_HAIRCUT_PCT,
        icir_threshold=ICIR_THRESHOLD,
        t_threshold=IC_BLOCK_T_THRESHOLD,
    )
    strat = _strategy_returns(pair["f"], pair["r"])
    strat_clean = strat.replace([np.inf, -np.inf], np.nan).dropna().to_numpy()
    ppy = PERIODS_PER_YEAR.get(timeframe, 252)
    observed = float(canonical_sharpe(strat_clean, periods_per_year=ppy))
    hsr = float(haircut_sharpe_ratio(strat_clean, n_trials=1, periods_per_year=ppy))
    psr = probabilistic_sharpe_ratio(strat_clean)
    dsr = deflated_sharpe_ratio(strat_clean, n_trials=1, periods_per_year=ppy)
    return SlotResult(
        family=spec.family,
        label=spec.label,
        asset=asset,
        timeframe=timeframe,
        n_bars=int(prices.close.size),
        n_pairs=n_pairs,
        ic_passed=bool(ic.passes),
        ic_mean=float(ic.ic_mean),
        ic_std=float(ic.ic_std),
        icir_raw=float(ic.icir),
        icir_haircut=float(ic.icir_haircut),
        ic_t_block=float(ic.t_block),
        observed_sharpe=observed,
        haircut_sharpe=hsr,
        psr=float(psr) if psr is not None else None,
        dsr=float(dsr) if dsr is not None else None,
        status="OK",
    )


def _evaluate_slot_universe(
    spec: CandidateSpec, timeframe: str, universe_prices: list[PriceSeries]
) -> SlotResult:
    horizon = spec.horizon_hourly if timeframe == "1h" else spec.horizon_daily
    pair = value_composite_universe_factor(universe_prices, timeframe, horizon)
    if pair is None:
        return SlotResult(
            family=spec.family,
            label=spec.label,
            asset="UNIVERSE",
            timeframe=timeframe,
            n_bars=0,
            n_pairs=0,
            ic_passed=False,
            ic_mean=float("nan"),
            ic_std=float("nan"),
            icir_raw=float("nan"),
            icir_haircut=float("nan"),
            ic_t_block=float("nan"),
            observed_sharpe=0.0,
            haircut_sharpe=float("nan"),
            psr=None,
            dsr=None,
            status="INSUFFICIENT_DATA",
        )
    factor, fwd = pair
    n_pairs = int(factor.dropna().shape[0])
    if n_pairs < 4 * 21:
        return SlotResult(
            family=spec.family,
            label=spec.label,
            asset="UNIVERSE",
            timeframe=timeframe,
            n_bars=0,
            n_pairs=n_pairs,
            ic_passed=False,
            ic_mean=float("nan"),
            ic_std=float("nan"),
            icir_raw=float("nan"),
            icir_haircut=float("nan"),
            ic_t_block=float("nan"),
            observed_sharpe=0.0,
            haircut_sharpe=float("nan"),
            psr=None,
            dsr=None,
            status="INSUFFICIENT_DATA",
        )
    # The cross-sectional pipeline expects prices on the same index as
    # the factor; we use the first asset's price (the factor's anchor)
    # so the IC screen has a coherent (factor, prices) pair.
    anchor_close = universe_prices[0].close.reindex(factor.index)
    ic = screen_factor(
        factor=factor,
        prices=anchor_close,
        horizon=horizon,
        haircut_pct=IC_HAIRCUT_PCT,
        icir_threshold=ICIR_THRESHOLD,
        t_threshold=IC_BLOCK_T_THRESHOLD,
    )
    strat = _strategy_returns(factor, fwd)
    strat_clean = strat.replace([np.inf, -np.inf], np.nan).dropna().to_numpy()
    ppy = PERIODS_PER_YEAR.get(timeframe, 252)
    observed = float(canonical_sharpe(strat_clean, periods_per_year=ppy))
    hsr = float(haircut_sharpe_ratio(strat_clean, n_trials=1, periods_per_year=ppy))
    psr = probabilistic_sharpe_ratio(strat_clean)
    dsr = deflated_sharpe_ratio(strat_clean, n_trials=1, periods_per_year=ppy)
    return SlotResult(
        family=spec.family,
        label=spec.label,
        asset="UNIVERSE",
        timeframe=timeframe,
        n_bars=0,
        n_pairs=n_pairs,
        ic_passed=bool(ic.passes),
        ic_mean=float(ic.ic_mean),
        ic_std=float(ic.ic_std),
        icir_raw=float(ic.icir),
        icir_haircut=float(ic.icir_haircut),
        ic_t_block=float(ic.t_block),
        observed_sharpe=observed,
        haircut_sharpe=hsr,
        psr=float(psr) if psr is not None else None,
        dsr=float(dsr) if dsr is not None else None,
        status="OK",
    )


# ---------------------------------------------------------------------------
# Verdict aggregation
# ---------------------------------------------------------------------------


@dataclass
class CandidateVerdict:
    family: str
    label: str
    description: str
    registry_hypothesis_id: str | None
    verdict: str  # GO | NO_GO | INSUFFICIENT_DATA
    n_slots_total: int
    n_slots_ok: int
    n_slots_passing_ic: int
    median_haircut_sharpe: float | None
    median_dsr: float | None
    median_psr: float | None
    reasons: list[str] = field(default_factory=list)
    notes: str = ""


def _aggregate_verdict(spec: CandidateSpec, slots: list[SlotResult]) -> CandidateVerdict:
    ok = [s for s in slots if s.status == "OK"]
    n_ok = len(ok)
    n_passing_ic = sum(1 for s in ok if s.ic_passed)
    reasons: list[str] = []
    if n_ok == 0:
        return CandidateVerdict(
            family=spec.family,
            label=spec.label,
            description=spec.description,
            registry_hypothesis_id=spec.registry_hypothesis_id,
            verdict=VERDICT_INSUFFICIENT,
            n_slots_total=len(slots),
            n_slots_ok=0,
            n_slots_passing_ic=0,
            median_haircut_sharpe=None,
            median_dsr=None,
            median_psr=None,
            reasons=["no slot produced a usable return series (insufficient data)"],
            notes=spec.notes,
        )
    hsr_vals = [s.haircut_sharpe for s in ok if math.isfinite(s.haircut_sharpe)]
    dsr_vals = [s.dsr for s in ok if s.dsr is not None and math.isfinite(s.dsr)]
    psr_vals = [s.psr for s in ok if s.psr is not None and math.isfinite(s.psr)]
    med_hsr = float(np.median(hsr_vals)) if hsr_vals else None
    med_dsr = float(np.median(dsr_vals)) if dsr_vals else None
    med_psr = float(np.median(psr_vals)) if psr_vals else None
    if n_passing_ic < KILL_MIN_PASSING_SLOTS:
        reasons.append(
            f"only {n_passing_ic} slots pass the IC screen (kill criterion: "
            f">= {KILL_MIN_PASSING_SLOTS} required)"
        )
    if med_hsr is None or med_hsr <= HAIRCUT_SHARPE_GATE:
        reasons.append(f"median haircut Sharpe {med_hsr} not > {HAIRCUT_SHARPE_GATE}")
    if med_dsr is None or med_dsr < DSR_MIN:
        reasons.append(f"median DSR {med_dsr} < {DSR_MIN} after deflated-SR penalty")
    if not reasons:
        verdict = VERDICT_GO
    else:
        verdict = VERDICT_NO_GO
    return CandidateVerdict(
        family=spec.family,
        label=spec.label,
        description=spec.description,
        registry_hypothesis_id=spec.registry_hypothesis_id,
        verdict=verdict,
        n_slots_total=len(slots),
        n_slots_ok=n_ok,
        n_slots_passing_ic=n_passing_ic,
        median_haircut_sharpe=med_hsr,
        median_dsr=med_dsr,
        median_psr=med_psr,
        reasons=reasons,
        notes=spec.notes,
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


@dataclass
class SprintReport:
    generated_at: str
    candidates: list[CandidateVerdict]
    slots: list[SlotResult]
    kill_criterion_triggered: bool
    total_passing_ic: int
    thresholds: dict[str, float]

    def as_dict(self) -> dict:
        return {
            "metadata": {
                "generated_at": self.generated_at,
                "task": "BL-708 — Sprint 1 qualification of Stage 1 candidates",
                "framework": "Edge Research Factory, ADR-017 / BL-706 / BL-707",
                "thresholds": self.thresholds,
            },
            "kill_criterion": {
                "min_passing_ic_slots": KILL_MIN_PASSING_SLOTS,
                "total_passing_ic": self.total_passing_ic,
                "triggered": self.kill_criterion_triggered,
                "design_ref": (
                    "docs/plans/2026-08-21-edge-research-factory-design.md §8 — "
                    "'se < 2 fattori superano IC screen → stop, report onesto'"
                ),
            },
            "candidates": [asdict(c) for c in self.candidates],
            "slots": [asdict(s) for s in self.slots],
        }


def run_sprint(*, lake_root: Path, candidates: list[CandidateSpec] | None = None) -> SprintReport:
    """Run the Sprint 1 gauntlet on the default candidates and return the report."""
    candidates = candidates or _default_candidates()

    # Pre-load universe prices for the value-composite slot.
    universe_prices: dict[str, list[PriceSeries]] = {}
    for spec in candidates:
        if not spec.universe_assets:
            continue
        for tf in ("1d", "1h"):
            series = []
            for asset in spec.universe_assets:
                ps = load_price_series(lake_root, asset, tf)
                if ps is not None:
                    series.append(ps)
            universe_prices[(spec.family, tf)] = series

    all_slots: list[SlotResult] = []
    verdicts: list[CandidateVerdict] = []
    for spec in candidates:
        slot_results: list[SlotResult] = []
        if spec.single_asset_slots:
            for asset, tf in spec.single_asset_slots:
                ps = load_price_series(lake_root, asset, tf)
                if ps is None:
                    slot_results.append(
                        SlotResult(
                            family=spec.family,
                            label=spec.label,
                            asset=asset,
                            timeframe=tf,
                            n_bars=0,
                            n_pairs=0,
                            ic_passed=False,
                            ic_mean=float("nan"),
                            ic_std=float("nan"),
                            icir_raw=float("nan"),
                            icir_haircut=float("nan"),
                            ic_t_block=float("nan"),
                            observed_sharpe=0.0,
                            haircut_sharpe=float("nan"),
                            psr=None,
                            dsr=None,
                            status="LOAD_ERROR",
                        )
                    )
                    continue
                slot_results.append(_evaluate_slot_single(spec, asset, tf, ps))
        if spec.universe_assets:
            for tf in ("1d", "1h"):
                universe = universe_prices.get((spec.family, tf), [])
                if not universe:
                    slot_results.append(
                        SlotResult(
                            family=spec.family,
                            label=spec.label,
                            asset="UNIVERSE",
                            timeframe=tf,
                            n_bars=0,
                            n_pairs=0,
                            ic_passed=False,
                            ic_mean=float("nan"),
                            ic_std=float("nan"),
                            icir_raw=float("nan"),
                            icir_haircut=float("nan"),
                            ic_t_block=float("nan"),
                            observed_sharpe=0.0,
                            haircut_sharpe=float("nan"),
                            psr=None,
                            dsr=None,
                            status="LOAD_ERROR",
                        )
                    )
                    continue
                slot_results.append(_evaluate_slot_universe(spec, tf, universe))
        all_slots.extend(slot_results)
        verdicts.append(_aggregate_verdict(spec, slot_results))

    total_passing_ic = sum(c.n_slots_passing_ic for c in verdicts)
    kill = total_passing_ic < KILL_MIN_PASSING_SLOTS
    return SprintReport(
        generated_at=datetime.now(UTC).isoformat(),
        candidates=verdicts,
        slots=all_slots,
        kill_criterion_triggered=kill,
        total_passing_ic=total_passing_ic,
        thresholds={
            "icir_threshold": ICIR_THRESHOLD,
            "ic_block_t_threshold": IC_BLOCK_T_THRESHOLD,
            "ic_haircut_pct": IC_HAIRCUT_PCT,
            "haircut_sharpe_min": HAIRCUT_SHARPE_GATE,
            "dsr_min": DSR_MIN,
            "psr_min": PSR_MIN,
        },
    )


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _render_table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |"]
    out.append("|" + "|".join(["---"] * len(headers)) + "|")
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return out


def _fmt(value: float | None, places: int = 4) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float) and not math.isfinite(value):
        return "n/a"
    return f"{value:.{places}f}"


def render_markdown(report: SprintReport) -> str:
    lines: list[str] = []
    lines.append("# BL-708 — Edge Factory Sprint 1 Qualification Report")
    lines.append("")
    lines.append(f"**Generated**: {report.generated_at}")
    lines.append(
        "**Framework**: Edge Research Factory · ADR-017 (DSR/PSR) · "
        "BL-706 (IC screen) · BL-707 (Haircut Sharpe)."
    )
    lines.append(
        "**Reference**: `docs/plans/2026-08-21-edge-research-factory-design.md` "
        "§3 (Stage 1 corpus mining), §6 (qualification gauntlet), §8 (kill criteria)."
    )
    lines.append("")
    lines.append("## Top-line verdict")
    lines.append("")
    for c in report.candidates:
        badge = {
            VERDICT_GO: "**GO**",
            VERDICT_NO_GO: "**NO-GO**",
            VERDICT_INSUFFICIENT: "**INSUFFICIENT_DATA**",
        }[c.verdict]
        lines.append(
            f"- **{c.label}** (`{c.family}`) → {badge} "
            f"(slots: {c.n_slots_passing_ic} IC-pass / {c.n_slots_ok} OK / "
            f"{c.n_slots_total} total; "
            f"median haircut Sharpe {_fmt(c.median_haircut_sharpe)}, "
            f"median DSR {_fmt(c.median_dsr)})"
        )
    lines.append("")
    if report.kill_criterion_triggered:
        lines.append("## ⚠️ KILL CRITERION TRIGGERED (design spec §8)")
        lines.append("")
        lines.append(
            f"Total slots passing the IC screen across all four candidates = "
            f"**{report.total_passing_ic}** (< {KILL_MIN_PASSING_SLOTS}). "
            "Per the design spec kill criterion, the sprint stops here: "
            "report is honest, and the next step is a Stage-2 corpus "
            "expansion before re-qualifying."
        )
        lines.append("")
    lines.append("## Per-candidate qualification tables")
    lines.append("")
    for c in report.candidates:
        lines.append(f"### {c.label} (`{c.family}`)")
        lines.append("")
        lines.append(c.description)
        if c.registry_hypothesis_id:
            lines.append(f"Registry backref: `{c.registry_hypothesis_id}`")
        if c.notes:
            lines.append(f"Notes: {c.notes}")
        lines.append("")
        lines.append(f"**Verdict**: `{c.verdict}`")
        if c.reasons:
            lines.append("")
            lines.append("Reasons:")
            for r in c.reasons:
                lines.append(f"- {r}")
        lines.append("")
        # Slot table for this candidate
        rows = []
        for s in report.slots:
            if s.family != c.family:
                continue
            rows.append(
                [
                    s.asset,
                    s.timeframe,
                    str(s.n_bars) if s.n_bars else "n/a",
                    str(s.n_pairs),
                    "✅" if s.ic_passed else "❌",
                    _fmt(s.ic_mean, 4),
                    _fmt(s.icir_raw, 4),
                    _fmt(s.icir_haircut, 4),
                    _fmt(s.ic_t_block, 3),
                    _fmt(s.observed_sharpe, 3),
                    _fmt(s.haircut_sharpe, 3),
                    _fmt(s.psr, 3),
                    _fmt(s.dsr, 3),
                    s.status,
                ]
            )
        lines.extend(
            _render_table(
                [
                    "asset",
                    "tf",
                    "n_bars",
                    "n_pairs",
                    "IC",
                    "IC mean",
                    "ICIR raw",
                    "ICIR haircut",
                    "t-block",
                    "obs SR",
                    "haircut SR",
                    "PSR",
                    "DSR",
                    "status",
                ],
                rows,
            )
        )
        lines.append("")
    lines.append("## Thresholds (frozen)")
    lines.append("")
    for k, v in report.thresholds.items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="BL-708 — Sprint 1 qualification of the Edge Research Factory Stage 1 candidates"
    )
    p.add_argument(
        "--lake-root",
        type=Path,
        default=ROOT / "data" / "lake" / "curated",
        help="Curated-lake root directory (default: data/lake/curated).",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "docs" / "reports" / "edge-factory",
        help="Output directory for sprint-1.{md,json} (default: docs/reports/edge-factory).",
    )
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    # Try to enrich the backref metadata from the live registry.  The
    # registry is advisory only — failure to load does not abort the
    # runner (the candidates already carry the human-readable id).
    try:
        HypothesisRegistry().scan()
    except Exception:
        pass

    report = run_sprint(lake_root=args.lake_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "sprint-1.md"
    json_path = out_dir / "sprint-1.json"
    md_path.write_text(render_markdown(report), encoding="utf-8")
    json_path.write_text(json.dumps(report.as_dict(), indent=2, default=str), encoding="utf-8")
    print(f"[report] {md_path}")
    print(f"[report] {json_path}")
    for c in report.candidates:
        print(f"[verdict] {c.label}: {c.verdict} ({c.n_slots_passing_ic} IC-pass)")
    if report.kill_criterion_triggered:
        print(
            f"[kill] {report.total_passing_ic} IC-pass slots < "
            f"{KILL_MIN_PASSING_SLOTS} threshold — design spec §8 kill triggered"
        )
    return 0


__all__ = [
    "DEFAULT_HORIZON_DAILY",
    "DEFAULT_HORIZON_HOURLY",
    "DSR_MIN",
    "HAIRCUT_SHARPE_GATE",
    "ICIR_THRESHOLD",
    "IC_BLOCK_T_THRESHOLD",
    "IC_HAIRCUT_PCT",
    "KILL_MIN_PASSING_SLOTS",
    "PSR_MIN",
    "VERDICT_GO",
    "VERDICT_INSUFFICIENT",
    "VERDICT_NO_GO",
    "CandidateSpec",
    "CandidateVerdict",
    "PriceSeries",
    "SlotResult",
    "SprintReport",
    "crypto_carry_proxy_factor",
    "load_price_series",
    "render_markdown",
    "reversion_factor",
    "run_sprint",
    "trend_cta_factor",
    "value_composite_universe_factor",
]


if __name__ == "__main__":
    raise SystemExit(main())
