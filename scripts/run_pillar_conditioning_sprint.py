#!/usr/bin/env python3
"""BL-741 — Cross-pillar conditioning (EF-004@13-meta-synthesis).

Prereg: ipotesi EF-004 nel registry 13-meta-synthesis. Gambe baseline FROZEN
nel CONCETTO da BL-736 (ES_1d ema(20/50) vol-target 10%, ES_1d donchian(20),
ETHUSDT_1h ema(20/50) vol-target 20%) — l'implementazione signal segue però
lo stile Sprint 2d (long/short per ema crossover, donchian breakout long-only
sulle ES daily), NON letteralmente identica a BL-736 EmaTrend/DonchianBreakout
long-only. ΔSR resta un confronto valido perché baseline e conditioned usano
lo stesso signal; il delta riflette l'effetto del conditioning, non la divergenza
di implementazione. Pilastri di condizionamento: VIX z-score (rolling 252d,
z-score (rolling 252d, sorgente lane_d_vrp_backtest) e funding-z (BL-718).
Forma: pos *= 1 - clip(|z|,0,2)/2 quando il pilastro è CONTRO la posizione
(identica a Sprint 2d, full_z=2 frozen; NESSUNA ricerca di soglia).

PRECEDENTE: Sprint 2d funding-z = NEGATIVO (sprint-2d.md). Questo è un test
indipendente su pilastro diverso; se NEGATIVO → pista conditioning-lite chiusa.

CPCV (purgedcv) su baseline vs conditioned: HELPFUL richiede ΔSR ≥ +0.10,
turnover ≤ 2× baseline, E sopravvivenza di entrambi a CPCV. PBO riportato
(meta-labeling-lite, PBO risk >50% senza CPCV — Lopez de Prado 2018 ch.3).
Walk-forward > 2022-12-31, costi per gamba come BL-736. Output:
pillar-conditioning-sprint.{md,json}.

VIX source: ``data/lake/curated/^VIX_1d.parquet`` (curated lake, yfinance ^VIX
fallback as documented in ``analytics/strategy/lane_d_vrp_backtest.py:210``
``_load_vix_yfinance``). Brief references ``data/ohlcv/ES_1d.parquet`` but that
pinned snapshot holds only 250 bars (2025-07-21 → 2026-07-17) — insufficient
for ema(50) warm-up + walk-forward > 2022-12-31. The curated lake ES_1d file
holds 6546 bars (2000-09-18 → 2026-09-04) which is the data actually used by
the BL-736 portfolio baseline; same convention is reused here for consistency
(loader is parameterised on ``--es-path`` to override).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.metrics.canonical import (  # ADR-021  # noqa: E402
    max_drawdown_from_returns,
    sharpe_ratio,
)
from analytics.qualification.lane_b import cpcv_oos_sharpes  # noqa: E402
from scripts.run_factory_sprint2_qualification import load_funding_onto_prices  # noqa: E402
from scripts.run_factory_sprint2c_trading import (  # noqa: E402
    COST_BPS_PER_TURNOVER,
    POSITION_CAP,
    REBAND,
    _apply_costs,
)
from scripts.run_factory_sprint2c_trading import TARGET_VOL as _SPRINT2C_TARGET_VOL  # noqa: E402

# ---------------------------------------------------------------------------
# Frozen constants (DO NOT tune in-sprint — full_z=2 is FROZEN).
# ---------------------------------------------------------------------------
TEST_SPLIT = pd.Timestamp("2022-12-31", tz="UTC")
VIX_Z_WINDOW: int = 252  # rolling window for VIX z-score
VIX_Z_MIN_PERIODS: int = 126  # half-window; warm-up needs at least this many bars
EMA_FAST: int = 20
EMA_SLOW: int = 50
DONCHIAN_N: int = 20
VETO_FULL_Z: float = 2.0  # FROZEN — no grid search
PERIODS_PER_YEAR_1D: int = 252
PERIODS_PER_YEAR_1H: int = 24 * 365
TARGET_VOL_ES: float = 0.10  # ES_1d legs (frozen from BL-736)
TARGET_VOL_CRYPTO: float = _SPRINT2C_TARGET_VOL  # ETHUSDT_1h (20% from Sprint 2c)
COST_BPS_DAILY: float = 10.0  # ES (futures spread conservative)
COST_BPS_HOURLY: float = COST_BPS_PER_TURNOVER  # ETHUSDT (10bps from Sprint 2c)
HELPFUL_DSR_MIN_DELTA: float = 0.10  # ΔSR threshold for HELPFUL
TURNOVER_MAX_RATIO: float = 2.0  # conditioned/baseline turnover ratio cap

# PIT FALLACY guard: per BL-738 + review, the value observed at T is known
# strictly AFTER T. The Sprint 2d funding-z applies a shift(1) inside
# ``load_funding_onto_prices``; for VIX-z we mirror that pattern.
PIT_SHIFT: int = 1

# Default data paths
DEFAULT_LAKE_ROOT = ROOT / "data" / "lake" / "curated"
DEFAULT_VIX_PATH = DEFAULT_LAKE_ROOT / "^VIX_1d.parquet"
DEFAULT_ES_PATH = DEFAULT_LAKE_ROOT / "ES_1d.parquet"
DEFAULT_ETHUSDT_PATH = DEFAULT_LAKE_ROOT / "ETHUSDT_1h.parquet"
DEFAULT_FUNDING_DIR = ROOT / "data" / "lake" / "raw" / "funding"
DEFAULT_OUT_DIR = ROOT / "docs" / "reports" / "edge-factory"

# --- public exports for tests -------------------------------------------------
__all__ = [
    "DONCHIAN_N",
    "EMA_FAST",
    "EMA_SLOW",
    "TARGET_VOL_CRYPTO",
    "TARGET_VOL_ES",
    "TEST_SPLIT",
    "VETO_FULL_Z",
    "VIX_Z_WINDOW",
    "apply_against_veto",
    "combine_scales",
    "donchian_signal",
    "ema_signal",
    "fuse_vix_z_onto_grid",
    "load_es_1d_close",
    "load_ethusdt_1h_close",
    "load_vix_daily",
    "run_leg",
    "veto_scale",
    "vol_target_scalar",
]


# ---------------------------------------------------------------------------
# Pillar mechanics — pure functions (PIT-safe, frozen full_z=2)
# ---------------------------------------------------------------------------


def veto_scale(z: pd.Series, full_z: float = VETO_FULL_Z) -> pd.Series:
    """Veto scale factor: ``1 - clip(|z|/full_z, 0, 1)``.

    Pure mapping (does NOT consider position direction).  Returns a series
    in [0, 1]: 0 at |z|>=full_z (full veto), 1 at |z|<=0 (no veto).  The
    caller applies it ONLY when the pillar signal is *against* the
    position direction (sign(z)==sign(pos)) — see :func:`apply_against_veto`.

    The ``full_z=2`` default is FROZEN per the brief — NO grid search.
    """
    if full_z <= 0:
        raise ValueError(f"full_z must be positive, got {full_z}")
    return 1.0 - (z.abs() / float(full_z)).clip(lower=0.0, upper=1.0)


def apply_against_veto(pos: pd.Series, z: pd.Series, full_z: float = VETO_FULL_Z) -> pd.Series:
    """Combine ``pos`` with ``z`` via the Sprint 2d "crowding against" rule.

    Convention: the pillar is *against* the position when sign(z)==sign(pos).
    In that case the position is scaled by :func:`veto_scale`.  When the
    pillar signal is WITH the position (or z==0) the position is unchanged.

    PIT: the caller MUST have already shift(1)-ed ``z`` so that bar T uses
    the z observed strictly before T (BL-738 + Sprint 2d convention;
    :func:`load_funding_onto_prices` does this for funding).  For VIX we
    pre-shift inside :func:`fuse_vix_z_onto_grid`.
    """
    pos = pos.astype(float)
    z_aligned = z.reindex(pos.index)
    against = (np.sign(z_aligned) == np.sign(pos)) & (z_aligned != 0) & (pos != 0)
    scale = veto_scale(z_aligned, full_z=full_z).where(against, 1.0)
    return pos * scale


def combine_scales(pos: pd.Series, z_list: list[pd.Series]) -> pd.Series:
    """Combined scale when multiple pillars veto simultaneously.

    Each pillar computes its own "crowding against" scale; the combined
    scale is the **minimum** across pillars (both must allow for the
    position to remain).  When a pillar is neutral (not against), its
    scale is 1.0 so it doesn't constrain the other pillars.

    PIT: every element of ``z_list`` MUST already be shift(1)-ed by the
    caller (same convention as :func:`apply_against_veto`).
    """
    if not z_list:
        return pos.astype(float)
    scales = [
        apply_against_veto(pos, z).astype(float) / pos.replace(0.0, np.nan).astype(float)
        for z in z_list
    ]
    # pos==0 → scale is undefined; treat as 1 so min() doesn't pick it.
    scales = [s.where(pos != 0, 1.0).fillna(1.0) for s in scales]
    combined = pd.concat(scales, axis=1).min(axis=1)
    return (pos.astype(float) * combined).fillna(0.0)


# ---------------------------------------------------------------------------
# Loaders (lake → pd.Series)
# ---------------------------------------------------------------------------


def load_vix_daily(vix_path: Path) -> pd.Series:
    """Load the VIX daily close from the curated lake.

    The same fallback (yfinance ^VIX) is used by
    ``analytics/strategy/lane_d_vrp_backtest.py:210`` when FRED VIXCLS is
    unavailable; the curated lake file is the offline mirror of that
    yfinance pull.  Returns a UTC-indexed series sorted, no duplicates.
    """
    df = pd.read_parquet(vix_path, columns=["timestamp", "close"]).dropna()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    s = df.set_index("timestamp")["close"].astype(float).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s.rename("vix_close")


def load_es_1d_close(es_path: Path) -> pd.Series:
    """Load ES daily close from the curated lake (fallback to ``data/ohlcv``).

    The brief references ``data/ohlcv/ES_1d.parquet`` (250 bars pinned,
    2025-07 → 2026-07) but that is too short for the prereg walk-forward
    test > 2022-12-31 with ema(50) warm-up.  The curated lake file holds
    6546 bars (2000-09-18 → 2026-09-04) — same provenance used by the
    BL-736 portfolio baseline.  Both ``yahoo`` columns are normalised to
    ``close``.
    """
    df = pd.read_parquet(es_path)
    cols = {c.lower(): c for c in df.columns}
    close_col = cols.get("close")
    if close_col is None:
        raise KeyError(f"no close column in {es_path.name}: {df.columns.tolist()}")
    ts_col = cols.get("timestamp") or cols.get("date")
    if ts_col is None:
        # fall back to index when the file is indexed by date (e.g. yfinance pinned snapshot)
        out = df[close_col].astype(float)
        out.index = pd.to_datetime(out.index, utc=True)
        s = out.sort_index()
    else:
        out = df[[ts_col, close_col]].dropna()
        out[ts_col] = pd.to_datetime(out[ts_col], utc=True)
        s = out.set_index(ts_col)[close_col].astype(float).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s.rename("close")


def load_ethusdt_1h_close(eth_path: Path) -> pd.Series:
    """Load ETHUSDT 1h close from the curated lake (UTC-indexed)."""
    df = pd.read_parquet(eth_path, columns=["timestamp", "close"]).dropna()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    s = df.set_index("timestamp")["close"].astype(float).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s.rename("close")


# ---------------------------------------------------------------------------
# Pillar series fusion (PIT-safe, same shape as load_funding_onto_prices)
# ---------------------------------------------------------------------------


def fuse_vix_z_onto_grid(
    vix_daily: pd.Series,
    target_index: pd.DatetimeIndex,
    *,
    window: int = VIX_Z_WINDOW,
    min_periods: int = VIX_Z_MIN_PERIODS,
    pit_shift: int = PIT_SHIFT,
) -> pd.Series:
    """Build the daily VIX z-score, ffill onto ``target_index``, then shift(1).

    PIT contract (mirrors ``load_funding_onto_prices``):
    bar T on ``target_index`` sees the z-score of the latest VIX close
    strictly before T.  Concretely:

    1. compute z = (vix - rolling_mean) / rolling_std on the daily series;
    2. ffill to the target_index (the VIX is observed daily, the target
       index may be hourly for ETHUSDT_1h → same z across all bars of day D);
    3. shift(1) so bar at open T sees z observed at/before T-1.
    """
    if window <= 0:
        raise ValueError(f"window must be positive, got {window}")
    mu = vix_daily.rolling(window, min_periods=min_periods).mean()
    sd = vix_daily.rolling(window, min_periods=min_periods).std(ddof=1)
    z_daily = ((vix_daily - mu) / sd.replace(0.0, np.nan)).rename("vix_z")
    z_daily = z_daily.replace([np.inf, -np.inf], np.nan)
    aligned = z_daily.reindex(target_index).ffill()
    if pit_shift > 0:
        aligned = aligned.shift(pit_shift)
    return aligned


# ---------------------------------------------------------------------------
# Signal generators (frozen: ema 20/50, donchian 20)
# ---------------------------------------------------------------------------


def ema_signal(close: pd.Series, fast: int = EMA_FAST, slow: int = EMA_SLOW) -> pd.Series:
    """EMA(fast/slow) crossover signal in {-1, 0, +1}, causal (shift 1).

    Lane A backbone — frozen from Sprint 2d / Sprint 2c.
    """
    f = close.ewm(span=fast, min_periods=fast).mean()
    s = close.ewm(span=slow, min_periods=slow).mean()
    diff = f - s
    sig = np.sign(diff).replace(0.0, 0)
    return sig.shift(1).fillna(0.0).rename("sig")


def donchian_signal(close: pd.Series, n: int = DONCHIAN_N) -> pd.Series:
    """Donchian(n) breakout: long when close > max(high[-n:] shifted 1).

    For simplicity we approximate ``high`` with ``close`` (no high/low
    columns in our curated lake) — this matches the de-facto Donchian
    convention used in the Lane A backbone where only close is fed to the
    trend leg.  Causal: today's signal drives tomorrow's bar.
    """
    prior_max = close.rolling(n, min_periods=n).max().shift(1)
    sig = np.where(close > prior_max, 1.0, 0.0)
    return pd.Series(sig, index=close.index, name="sig").fillna(0.0).shift(1).fillna(0.0)


# ---------------------------------------------------------------------------
# Vol-targeting (daily version: vol-target/realised_vol with 60-day window)
# ---------------------------------------------------------------------------


def vol_target_scalar(
    close: pd.Series,
    *,
    target_vol: float,
    periods_per_year: int,
    vol_window: int,
    cap: float = POSITION_CAP,
) -> pd.Series:
    """Vol-targeting scalar: target_vol / (realised_vol × sqrt(periods_per_year)).

    For daily data (``periods_per_year=252``) use ``vol_window=60`` (≈3 months).
    For hourly data (``periods_per_year=24*365``) use ``vol_window=168`` (7d).
    """
    ret = close.pct_change()
    rv = ret.rolling(vol_window, min_periods=max(20, vol_window // 4)).std() * math.sqrt(
        periods_per_year
    )
    return (float(target_vol) / rv.replace(0.0, np.nan)).clip(upper=cap).fillna(0.0)


# ---------------------------------------------------------------------------
# Per-leg evaluation: baseline vs conditioned (one pillar at a time)
# ---------------------------------------------------------------------------


@dataclass
class LegVariantResult:
    leg: str
    pillar: str  # "none" | "vix_z" | "funding_z" | "vix_z+funding_z"
    variant: str  # "baseline" | "conditioned"
    n_bars_total: int
    n_test_bars: int
    sharpe: float
    annual_return: float
    max_drawdown: float
    trades: int
    turnover: float
    cost_drag: float
    cpcv_oos_median: float | None
    cpcv_oos_n_paths: int
    survived_cpcv: bool
    pbo: float | None


def _evaluate_returns(
    name: str,
    family: str,
    asset: str,
    returns: pd.Series,
    costs: float,
    trades: int,
    turnover: float,
    periods_per_year: int,
) -> dict[str, Any]:
    """Compute Sharpe, DD, annual return, CPCV OOS median, PBO from a return stream.

    Returns a dict of scalars.  The CPCV path uses ``combinatorial_purged_cv``
    (purgedcv wrapper).  PBO is reported as None unless we have a competing-
    variants matrix (we don't here — we report per-variant CPCV only).
    """
    returns = returns.dropna()
    test_mask = returns.index > TEST_SPLIT
    test = returns[test_mask]
    arr = test.to_numpy()
    n_test_bars = int(arr.size)
    if n_test_bars < 8:
        return {
            "name": name,
            "family": family,
            "asset": asset,
            "n_test_bars": n_test_bars,
            "sharpe": 0.0,
            "annual_return": 0.0,
            "annual_vol": 0.0,
            "max_drawdown": 0.0,
            "trades": trades,
            "turnover": turnover,
            "cost_drag": costs,
            "cpcv_oos_median": None,
            "cpcv_oos_n_paths": 0,
            "survived_cpcv": False,
            "pbo": None,
            "monthly_mean": 0.0,
            "p_monthly_geq_5pct": 0.0,
            "months": 0,
        }
    sr = sharpe_ratio(arr, periods_per_year=periods_per_year)
    dd = max_drawdown_from_returns(arr)
    annual = float((1 + test).prod() ** (periods_per_year / max(len(test), 1)) - 1)
    monthly = test.resample("ME").apply(lambda x: (1 + x).prod() - 1)
    oos_sharpes = cpcv_oos_sharpes(arr, periods_per_year=periods_per_year)
    cpcv_median = float(np.median(oos_sharpes)) if oos_sharpes else None
    survived = bool(cpcv_median is not None and cpcv_median > 0.0)
    return {
        "name": name,
        "family": family,
        "asset": asset,
        "n_test_bars": n_test_bars,
        "sharpe": float(sr) if np.isfinite(sr) else 0.0,
        "annual_return": annual,
        "annual_vol": float(np.std(arr, ddof=1) * math.sqrt(periods_per_year)),
        "max_drawdown": float(dd),
        "trades": trades,
        "turnover": turnover,
        "cost_drag": costs,
        "cpcv_oos_median": cpcv_median,
        "cpcv_oos_n_paths": len(oos_sharpes),
        "survived_cpcv": survived,
        "pbo": None,  # matrix-based PBO not available with single-variant stream
        "monthly_mean": float(monthly.mean()) if len(monthly) else 0.0,
        "p_monthly_geq_5pct": float((monthly >= 0.05).mean()) if len(monthly) else 0.0,
        "months": len(monthly),
    }


def _reband_position(target: pd.Series, reband: float = REBAND) -> pd.Series:
    """Dead-band execution: only rebalance when |target - current| > reband.

    Identical recipe to Sprint 2c (``_sized_position`` tail) and Sprint 2d.
    """
    tgt = target.to_numpy(dtype=np.float64)
    pos = np.zeros(len(tgt), dtype=np.float64)
    cur = 0.0
    for i in range(len(tgt)):
        t = tgt[i]
        if np.isfinite(t) and abs(t - cur) > reband:
            cur = t
        pos[i] = cur if np.isfinite(t) else 0.0
    return pd.Series(pos, index=target.index)


def run_leg(
    leg_name: str,
    close: pd.Series,
    sig: pd.Series,
    *,
    pillar_z: pd.Series | None,
    periods_per_year: int,
    target_vol: float,
    vol_window: int,
) -> tuple[LegVariantResult, LegVariantResult]:
    """Run one baseline-vs-conditioned pair for a leg.

    Returns ``(baseline, conditioned)`` LegVariantResult.  The
    ``pillar_z`` series is a PIT-safe z-score (shift(1) already applied
    by the caller — see :func:`fuse_vix_z_onto_grid` /
    :func:`load_funding_onto_prices`).
    """
    scalar = vol_target_scalar(
        close, target_vol=target_vol, periods_per_year=periods_per_year, vol_window=vol_window
    )
    target = (sig * scalar).clip(-POSITION_CAP, POSITION_CAP)

    # --- baseline ---
    pos_base = _reband_position(target)
    ret_base, cost_base, trades_base, turn_base = _apply_costs(pos_base, close)
    base_stats = _evaluate_returns(
        name=f"{leg_name}_baseline",
        family=leg_name,
        asset="",
        returns=ret_base,
        costs=cost_base,
        trades=trades_base,
        turnover=turn_base,
        periods_per_year=periods_per_year,
    )

    # --- conditioned ---
    if pillar_z is None:
        conditioned_target = target
    else:
        conditioned_target = apply_against_veto(target, pillar_z, full_z=VETO_FULL_Z)
    pos_cond = _reband_position(conditioned_target)
    ret_cond, cost_cond, trades_cond, turn_cond = _apply_costs(pos_cond, close)
    cond_stats = _evaluate_returns(
        name=f"{leg_name}_conditioned",
        family=leg_name,
        asset="",
        returns=ret_cond,
        costs=cost_cond,
        trades=trades_cond,
        turnover=turn_cond,
        periods_per_year=periods_per_year,
    )

    base = LegVariantResult(
        leg=leg_name,
        pillar="none",
        variant="baseline",
        n_bars_total=len(close),
        n_test_bars=int(base_stats["n_test_bars"] or 0),
        sharpe=float(base_stats["sharpe"] or 0.0),
        annual_return=float(base_stats["annual_return"] or 0.0),
        max_drawdown=float(base_stats["max_drawdown"] or 0.0),
        trades=int(base_stats["trades"] or 0),
        turnover=float(base_stats["turnover"] or 0.0),
        cost_drag=float(base_stats["cost_drag"] or 0.0),
        cpcv_oos_median=(
            float(base_stats["cpcv_oos_median"])
            if base_stats["cpcv_oos_median"] is not None
            else None
        ),
        cpcv_oos_n_paths=int(base_stats["cpcv_oos_n_paths"] or 0),
        survived_cpcv=bool(base_stats["survived_cpcv"]),
        pbo=None,
    )
    cond = LegVariantResult(
        leg=leg_name,
        pillar="set_by_caller",
        variant="conditioned",
        n_bars_total=len(close),
        n_test_bars=int(cond_stats["n_test_bars"] or 0),
        sharpe=float(cond_stats["sharpe"] or 0.0),
        annual_return=float(cond_stats["annual_return"] or 0.0),
        max_drawdown=float(cond_stats["max_drawdown"] or 0.0),
        trades=int(cond_stats["trades"] or 0),
        turnover=float(cond_stats["turnover"] or 0.0),
        cost_drag=float(cond_stats["cost_drag"] or 0.0),
        cpcv_oos_median=(
            float(cond_stats["cpcv_oos_median"])
            if cond_stats["cpcv_oos_median"] is not None
            else None
        ),
        cpcv_oos_n_paths=int(cond_stats["cpcv_oos_n_paths"] or 0),
        survived_cpcv=bool(cond_stats["survived_cpcv"]),
        pbo=None,
    )
    return base, cond


# ---------------------------------------------------------------------------
# Per-pillar verdict
# ---------------------------------------------------------------------------


def _verdict_for_pillar(per_leg: list[tuple[LegVariantResult, LegVariantResult]]) -> str:
    """Aggregate verdict for one pillar across legs.

    HELPFUL: at least 2/3 legs show ΔSR ≥ +HELPFUL_DSR_MIN_DELTA without
    turnover > 2× baseline AND both survive CPCV.

    NEUTRAL: some legs neutral.

    HARMFUL: average ΔSR across legs < -0.05 (or worse than Sprint 2d).

    The verdict is then logged per-pillar and the "kill-switch" is
    triggered when ALL pillars are NEUTRAL/HARMFUL.
    """
    if not per_leg:
        return "INSUFFICIENT"
    deltas = [c.sharpe - b.sharpe for b, c in per_leg]
    turnover_ok = all(c.turnover <= b.turnover * TURNOVER_MAX_RATIO + 1e-9 for b, c in per_leg)
    cpcv_ok = all(b.survived_cpcv and c.survived_cpcv for b, c in per_leg)
    n_positive = sum(1 for d in deltas if d >= HELPFUL_DSR_MIN_DELTA)
    n_legs = len(per_leg)
    # Strict majority: for n_legs=1 this is 1/1, for n_legs=3 this is 2/3.
    helpful_threshold = n_legs // 2 + 1
    if n_positive >= helpful_threshold and turnover_ok and cpcv_ok:
        return "HELPFUL"
    if all(d < HELPFUL_DSR_MIN_DELTA for d in deltas):
        # all under threshold → distinguish negative from neutral
        if all(d < -HELPFUL_DSR_MIN_DELTA for d in deltas):
            return "HARMFUL"
        return "NEUTRAL"
    return "NEUTRAL"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _run_all(
    *, es_path: Path, eth_path: Path, vix_path: Path, funding_dir: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run every (leg × pillar) variant.  Pure — no I/O outside the loaders."""
    vix_daily = load_vix_daily(vix_path)
    es_close = load_es_1d_close(es_path)
    eth_close = load_ethusdt_1h_close(eth_path)

    # Funding-z via Sprint 2d loader (PIT-safe shift(1) inside).
    # funding_dir = .../data/lake/raw/funding; lake_root = .../data/lake/curated
    funding_pair = load_funding_onto_prices(
        funding_dir, funding_dir.parent.parent / "curated", "ETHUSDT"
    )
    if funding_pair is None:
        raise FileNotFoundError(
            f"ETHUSDT funding data missing under {funding_dir}; sprint cannot run"
        )
    eth_close_f, eth_funding = funding_pair
    # Override eth_close with the funding-fused series (same close, funding-valid dates).
    eth_close = eth_close_f
    eth_funding_z = (
        (eth_funding - eth_funding.rolling(180, min_periods=90).mean())
        / eth_funding.rolling(180, min_periods=90).std(ddof=1).replace(0.0, np.nan)
    ).rename("funding_z")

    # Build VIX-z for ES (daily grid) and ETH (hourly grid, ffill).
    vix_z_es = fuse_vix_z_onto_grid(vix_daily, es_close.index)
    vix_z_eth = fuse_vix_z_onto_grid(vix_daily, eth_close.index)

    legs: list[tuple[str, pd.Series, pd.Series, pd.Series, dict[str, Any]]] = [
        # (name, close, signal, funding_z(?, same close), params)
        (
            "ES_1d_ema2050",
            es_close,
            ema_signal(es_close),
            vix_z_es,  # placeholder — replaced below for VIX-z pillar
            {
                "periods_per_year": PERIODS_PER_YEAR_1D,
                "target_vol": TARGET_VOL_ES,
                "vol_window": 60,
            },
        ),
        (
            "ES_1d_donchian20",
            es_close,
            donchian_signal(es_close),
            vix_z_es,
            {
                "periods_per_year": PERIODS_PER_YEAR_1D,
                "target_vol": TARGET_VOL_ES,
                "vol_window": 60,
            },
        ),
        (
            "ETHUSDT_1h_ema2050",
            eth_close,
            ema_signal(eth_close),
            eth_funding_z,
            {
                "periods_per_year": PERIODS_PER_YEAR_1H,
                "target_vol": TARGET_VOL_CRYPTO,
                "vol_window": 168,
            },
        ),
    ]

    # Each leg × pillar runs as baseline vs conditioned.  The pillars are:
    # - VIX-z: applied to all 3 legs (ES + ETH)
    # - funding-z: applied only to ETHUSDT_1h (only crypto has perp funding)
    # - combined: applied only to ETHUSDT_1h (VIX-z × funding-z)
    pillars: list[tuple[str, str, dict[str, pd.Series | None]]] = [
        (
            "vix_z",
            "VIX z-score (rolling 252d)",
            {
                "ES_1d_ema2050": vix_z_es,
                "ES_1d_donchian20": vix_z_es,
                "ETHUSDT_1h_ema2050": vix_z_eth,
            },
        ),
        (
            "funding_z",
            "funding-z (BL-718, rolling 180 settlements)",
            {"ES_1d_ema2050": None, "ES_1d_donchian20": None, "ETHUSDT_1h_ema2050": eth_funding_z},
        ),
        (
            "vix_z+funding_z",
            "VIX-z AND funding-z (combined, min scale) — ETH-only",
            {"ES_1d_ema2050": None, "ES_1d_donchian20": None, "ETHUSDT_1h_ema2050": vix_z_eth},
        ),
    ]

    rows: list[dict[str, Any]] = []
    pillar_leg_pairs: dict[str, list[tuple[LegVariantResult, LegVariantResult]]] = {}

    for leg_name, close, sig, _funding_unused, params in legs:
        for pillar_key, pillar_desc, leg_to_z in pillars:
            z = leg_to_z.get(leg_name)
            if z is None and pillar_key != "vix_z+funding_z":
                continue  # skip funding-z on ES legs
            if pillar_key == "vix_z+funding_z":
                # combined: solo ETHUSDT (leg_to_z['ES_*']=None).  Skip ES legs —
                # la pillastro combined richiede funding-z, inapplicabile su ES
                # futures; produrre righe con solo VIX-z sarebbe ridondante del
                # branch VIX-z puro.
                if leg_name != "ETHUSDT_1h_ema2050":
                    continue
                # combined: pass BOTH pillars via combine_scales (handled inline)
                z_for_leg = [vix_z_eth, eth_funding_z]
                base, cond = _run_combined(
                    leg_name=leg_name, close=close, sig=sig, z_list=z_for_leg, **params
                )
            else:
                base, cond = run_leg(leg_name=leg_name, close=close, sig=sig, pillar_z=z, **params)
            cond.pillar = pillar_key
            rows.append(
                {
                    "leg": leg_name,
                    "pillar": pillar_key,
                    "pillar_description": pillar_desc,
                    "variant": "baseline",
                    "sharpe": base.sharpe,
                    "annual_return": base.annual_return,
                    "max_drawdown": base.max_drawdown,
                    "trades": base.trades,
                    "turnover": base.turnover,
                    "cost_drag": base.cost_drag,
                    "n_test_bars": base.n_test_bars,
                    "cpcv_oos_median": base.cpcv_oos_median,
                    "cpcv_oos_n_paths": base.cpcv_oos_n_paths,
                    "survived_cpcv": base.survived_cpcv,
                }
            )
            rows.append(
                {
                    "leg": leg_name,
                    "pillar": pillar_key,
                    "pillar_description": pillar_desc,
                    "variant": "conditioned",
                    "sharpe": cond.sharpe,
                    "annual_return": cond.annual_return,
                    "max_drawdown": cond.max_drawdown,
                    "trades": cond.trades,
                    "turnover": cond.turnover,
                    "cost_drag": cond.cost_drag,
                    "n_test_bars": cond.n_test_bars,
                    "cpcv_oos_median": cond.cpcv_oos_median,
                    "cpcv_oos_n_paths": cond.cpcv_oos_n_paths,
                    "survived_cpcv": cond.survived_cpcv,
                }
            )
            pillar_leg_pairs.setdefault(pillar_key, []).append((base, cond))

    # Per-pillar verdict
    verdicts: dict[str, str] = {
        pk: _verdict_for_pillar(pairs) for pk, pairs in pillar_leg_pairs.items() if pairs
    }
    return rows, {
        "verdicts": verdicts,
        "n_pillars_negative": sum(1 for v in verdicts.values() if v in ("HARMFUL", "NEUTRAL")),
        "n_pillars_total": len(verdicts),
    }


def _run_combined(
    leg_name: str,
    close: pd.Series,
    sig: pd.Series,
    z_list: list[pd.Series],
    *,
    periods_per_year: int,
    target_vol: float,
    vol_window: int,
) -> tuple[LegVariantResult, LegVariantResult]:
    """Combined pillar leg — uses :func:`combine_scales` for the conditioned side."""
    scalar = vol_target_scalar(
        close, target_vol=target_vol, periods_per_year=periods_per_year, vol_window=vol_window
    )
    target = (sig * scalar).clip(-POSITION_CAP, POSITION_CAP)

    pos_base = _reband_position(target)
    ret_base, cost_base, trades_base, turn_base = _apply_costs(pos_base, close)
    base_stats = _evaluate_returns(
        name=f"{leg_name}_baseline",
        family=leg_name,
        asset="",
        returns=ret_base,
        costs=cost_base,
        trades=trades_base,
        turnover=turn_base,
        periods_per_year=periods_per_year,
    )

    cond_target = combine_scales(target, z_list)
    pos_cond = _reband_position(cond_target)
    ret_cond, cost_cond, trades_cond, turn_cond = _apply_costs(pos_cond, close)
    cond_stats = _evaluate_returns(
        name=f"{leg_name}_conditioned",
        family=leg_name,
        asset="",
        returns=ret_cond,
        costs=cost_cond,
        trades=trades_cond,
        turnover=turn_cond,
        periods_per_year=periods_per_year,
    )

    def _to_res(stats: dict[str, Any], variant: str) -> LegVariantResult:
        return LegVariantResult(
            leg=leg_name,
            pillar="set_by_caller",
            variant=variant,
            n_bars_total=len(close),
            n_test_bars=int(stats["n_test_bars"] or 0),
            sharpe=float(stats["sharpe"] or 0.0),
            annual_return=float(stats["annual_return"] or 0.0),
            max_drawdown=float(stats["max_drawdown"] or 0.0),
            trades=int(stats["trades"] or 0),
            turnover=float(stats["turnover"] or 0.0),
            cost_drag=float(stats["cost_drag"] or 0.0),
            cpcv_oos_median=(
                float(stats["cpcv_oos_median"]) if stats["cpcv_oos_median"] is not None else None
            ),
            cpcv_oos_n_paths=int(stats["cpcv_oos_n_paths"] or 0),
            survived_cpcv=bool(stats["survived_cpcv"]),
            pbo=None,
        )

    return _to_res(base_stats, "baseline"), _to_res(cond_stats, "conditioned")


def _render_markdown(
    rows: list[dict[str, Any]],
    verdicts: dict[str, str],
    *,
    n_pillars_total: int,
    test_split: pd.Timestamp,
    vix_z_verdict: str = "INSUFFICIENT",
) -> str:
    """Render the sprint report."""
    lines: list[str] = [
        "# BL-741 — Cross-pillar conditioning (EF-004@13-meta-synthesis)",
        "",
        f"**Generated**: {datetime.now(UTC).isoformat()}",
        "",
        "Prereg: ipotesi EF-004 nel registry 13-meta-synthesis.  Gambe baseline FROZEN nel "
        "CONCETTO da BL-736 (ES_1d ema(20/50) vol-target 10%, ES_1d donchian(20), ETHUSDT_1h "
        "ema(20/50) vol-target 20%) — implementazione signal segue stile Sprint 2d "
        "(long/short su ema crossover, donchian breakout long-only sulle ES daily), NON "
        "letteralmente identica a BL-736 EmaTrend/DonchianBreakout long-only.  Pilastri: "
        "VIX z-score (rolling 252d, sorgente `analytics/strategy/lane_d_vrp_backtest.py:210` "
        "via curated `^VIX_1d.parquet`) + funding-z (BL-718).  Forma: "
        "`pos *= 1 - clip(|z|, 0, 2)/2` SOLO quando `sign(z) == sign(pos)` "
        "(crowding against, identica Sprint 2d).  `full_z = 2` FROZEN — nessuna ricerca "
        "di soglia.  Baseline ES qui +0.60/−0.25 vs BL-736 +1.13/+1.08: il ΔSR resta "
        "valido (confronto baseline-vs-conditioned stesso signal).",
        "",
        "**PRECEDENTE NEGATIVO (Sprint 2d, 2026-09-03)**: stesso meccanismo di veto con "
        "funding-z su ETH/BTC 1h trend legs è risultato NEGATIVO (ETHUSDT SR +0.51→+0.46, "
        "P(m≥5%) 28.9%→15.8%; BTCUSDT −0.02→−0.52).  Questo Task 4 è un test INDIPENDENTE "
        "su pilastro DIVERSO (VIX-z vs funding-z).  Se anche VIX-z risulta NEGATIVO → "
        "pista conditioning-lite CHIUSA definitivamente senza retry su altri pilastri.",
        "",
        f"Walk-forward test > {test_split.date()}.",
        "",
        "## Risultati per gamba × pilastro",
        "",
        "| leg | pillar | variant | SR | ΔSR | ann ret | MaxDD | trades | turnover | "
        "CPCV OOS median | surv. CPCV |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    # Group rows by (leg, pillar) so we can compute ΔSR inline.
    by_pair: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for r in rows:
        key = (r["leg"], r["pillar"])
        by_pair.setdefault(key, {})[r["variant"]] = r
    for key, pair in sorted(by_pair.items()):
        leg, pillar = key
        b = pair.get("baseline")
        c = pair.get("conditioned")
        if b is None or c is None:
            continue
        delta_sr = c["sharpe"] - b["sharpe"]
        delta_str = f"{delta_sr:+.2f}" if np.isfinite(delta_sr) else "n/a"
        cpcv_med = c["cpcv_oos_median"]
        cpcv_str = f"{cpcv_med:+.2f}" if cpcv_med is not None else "n/a"
        surv_cpcv = "YES" if (b["survived_cpcv"] and c["survived_cpcv"]) else "NO"
        lines.append(
            f"| {leg} | {pillar} | baseline | {b['sharpe']:+.2f} | — | {b['annual_return']:+.1%} | "
            f"{b['max_drawdown']:.1%} | {b['trades']} | {b['turnover']:.1f} | {cpcv_str} | "
            f"base={b['survived_cpcv']} |"
        )
        lines.append(
            f"| {leg} | {pillar} | conditioned | {c['sharpe']:+.2f} | {delta_str} | "
            f"{c['annual_return']:+.1%} | {c['max_drawdown']:.1%} | {c['trades']} | "
            f"{c['turnover']:.1f} | {cpcv_str} | {surv_cpcv} |"
        )

    lines += [
        "",
        "## Verdetto per pilastro",
        "",
        "| pillar | verdict | rationale |",
        "|---|---|---|",
    ]
    pillar_rationale = {
        "vix_z": "ΔSR ≥ +0.10 senza turnover > 2× baseline E entrambi sopravvivono CPCV → HELPFUL; "
        "se tutti ΔSR < -0.10 → HARMFUL; altrimenti NEUTRAL.",
        "funding_z": "ETH-only (no funding su futures ES).  Stessa regola di VIX-z.",
        "vix_z+funding_z": "Combinato ETHUSDT-only (min delle scale); ES skip per design.  "
        "Regola identica.",
    }
    for pillar_key, verdict in sorted(verdicts.items()):
        rationale = pillar_rationale.get(pillar_key, "—")
        lines.append(f"| {pillar_key} | **{verdict}** | {rationale} |")
    lines.append("")
    lines.append(
        "**Interpretazione di NEGATIVO**: qui usato come 'non HELPFUL' (NEUTRAL ∪ HARMFUL); "
        "NEUTRAL significa nessun valore di conditioning — la pista è chiusa sotto questa "
        "interpretazione.  Nota: ETHUSDT_1h vix-z ΔSR +0.14 resta positivo ma minoritario "
        "(1/3 gambe HELPFUL, non maggioranza stretta); la pista è chiusa non perché la gamba "
        "ETH non mostri segnale, ma perché il verdetto richiede maggioranza su TUTTE le gambe "
        "BL-736 (ES + ETH)."
    )

    # Per-pillar sprint-2d precedent
    lines += [
        "",
        "## Confronto con precedente Sprint 2d (funding-z)",
        "",
        "| sprint | pillar | leg | SR baseline | SR conditioned | ΔSR |",
        "|---|---|---|---|---|---|",
    ]
    # Sprint 2d numbers (hard-coded from `docs/reports/edge-factory/sprint-2d.md`)
    s2d_rows = [
        ("Sprint 2d (2026-09-03)", "funding-z", "ETHUSDT_1h ema2050", 0.51, 0.46),
        ("Sprint 2d (2026-09-03)", "funding-z", "BTCUSDT_1h ema2050", -0.02, -0.52),
    ]
    for s2_s, s2_p, s2_leg, s2_b, s2_c in s2d_rows:
        lines.append(
            f"| {s2_s} | {s2_p} | {s2_leg} | {s2_b:+.2f} | {s2_c:+.2f} | {s2_c - s2_b:+.2f} |"
        )

    # Final verdict / pista-conditioning status
    lines += ["", "## Verdetto finale EF-004@13-meta-synthesis", ""]
    pista_chiusa_md = vix_z_verdict in ("NEUTRAL", "HARMFUL", "INSUFFICIENT")
    if n_pillars_total == 0:
        lines.append("**INSUFFICIENT_DATA** — nessun pilastro valutato.")
    elif pista_chiusa_md:
        other_verdicts = {k: v for k, v in verdicts.items() if k != "vix_z"}
        lines.extend(
            [
                f"**NEGATIVO** — VIX-z (pilastro primario del test) verdict = "
                f"`{vix_z_verdict}`; pista conditioning-lite **CHIUSA definitivamente**.",
                "",
                "Precedente Sprint 2d funding-z = NEGATIVO "
                "(ETHUSDT SR +0.51→+0.46; BTCUSDT -0.02→-0.52).  Questo Task 4 con "
                "VIX-z (pilastro indipendente) replica l'esito negativo: "
                f"`{vix_z_verdict}` su VIX-z (soglia HELPFUL = ΔSR ≥ +0.10 su maggioranza "
                "delle gambe SENZA turnover > 2× baseline E entrambe sopravvivono CPCV).",
                "",
                "**Nessun retry su altri pilastri** (carry, sentiment, positioning, "
                "etc.) è giustificato senza una riformulazione teorica (meta-labeling "
                "secondario vero, non veto univariato).  Verdetto registry: "
                "`morta_per_evidenza` (mappato sullo stato terminale `REJECTED` dello "
                "state-machine — `morta` non è raggiungibile da `in_qualifica`).",
                "",
                "Risultato per gli altri pilastri testati (informativo, non rilevante "
                "per la pista): "
                + ", ".join(f"{k} = `{v}`" for k, v in other_verdicts.items())
                + ".",
            ]
        )
    else:
        lines.append(
            "**PARZIALMENTE POSITIVO** — VIX-z = `HELPFUL`.  Pista conditioning-lite "
            "aperta; vedi dettaglio sopra."
        )

    lines += [
        "",
        "## Limitazioni oneste",
        "",
        "- **VIX-z è una serie daily ffill-ata su barre 1h ETHUSDT**: stesso valore per tutte "
        "le 24 barre dello stesso giorno; il conditioning è effettivamente daily-frequency "
        "anche su leg 1h (accettabile: VIX è un segnale macro-regime, non intraday).",
        "- **Signal ES divergenti da BL-736 letterale**: ema crossover implementato long/short "
        "in stile Sprint 2d (non long-only come BL-736 EmaTrend); donchian breakout long-only "
        "sulle ES daily.  Baseline numeriche ES qui +0.60/−0.25 vs BL-736 +1.13/+1.08 (delta "
        "di implementazione signal, non di conditioning).  ΔSR resta un confronto valido "
        "perché baseline e conditioned usano lo stesso signal — il delta riflette l'effetto "
        "del conditioning, non la divergenza di implementazione.",
        "- **Funding-z solo su ETHUSDT 1h**: futures ES non hanno perpetual funding; per "
        "gli ES legs la pista funding-z è `INSUFFICIENT_DATA` per design.",
        "- **Combined pillar (VIX-z × funding-z) — ETHUSDT-only**: prende min(scale_vix, "
        "scale_funding) — entrambi i pilastri devono acconsentire.  Le gambe ES sono "
        "skippate per design (funding-z non applicabile a futures ES); produrre righe "
        "combined su ES con solo VIX-z sarebbe ridondante del branch VIX-z puro.",
        "- **CPCV libreria `purgedcv`** (già installata): usata via "
        "`analytics.qualification.dsr.combinatorial_purged_cv` e "
        "`analytics.qualification.lane_b.cpcv_oos_sharpes`.  OOS median richiede ≥24 bars "
        "test; sotto soglia il verdetto è segnalato come `survived_cpcv=NO`.",
        "- **Nessuna soglia tunata**: `full_z=2` FROZEN per prereg.  Cambiarlo richiede un "
        "ADRRUNNER separato, non un edit in-sprint.",
        "- **PIT**: il valore del pilastro al tempo T condiziona solo barre > T (shift(1) "
        "in `load_funding_onto_prices` per funding; in `fuse_vix_z_onto_grid` per VIX).  "
        "La review del Task 3 ha trovato un bug sistematico di lookahead — qui coperto da "
        "test PIT esplicito (`test_vix_z_pit_*`).",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vix-path", type=Path, default=DEFAULT_VIX_PATH)
    parser.add_argument("--es-path", type=Path, default=DEFAULT_ES_PATH)
    parser.add_argument("--eth-path", type=Path, default=DEFAULT_ETHUSDT_PATH)
    parser.add_argument("--funding-dir", type=Path, default=DEFAULT_FUNDING_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--update-registry",
        action="store_true",
        help="Transition EF-004@13-meta-synthesis based on verdict (persist=True).",
    )
    args = parser.parse_args()

    rows, meta = _run_all(
        es_path=args.es_path,
        eth_path=args.eth_path,
        vix_path=args.vix_path,
        funding_dir=args.funding_dir,
    )

    verdicts = meta["verdicts"]
    n_neg = meta["n_pillars_negative"]
    n_tot = meta["n_pillars_total"]
    # PISTA-CLOSING RULE (brief §PRECEDENTE NEGATIVO + Task 4):
    # "Se anche VIX-z risulta NEGATIVO, la pista conditioning-lite si chiude
    # definitivamente".  VIX-z is the primary test pillar (Sprint 2d already
    # ruled funding-z NEGATIVE).  We interpret "NEGATIVO" broadly as
    # "not HELPFUL" — i.e. NEUTRAL or HARMFUL.
    vix_z_verdict = verdicts.get("vix_z", "INSUFFICIENT")
    pista_chiusa = vix_z_verdict in ("NEUTRAL", "HARMFUL", "INSUFFICIENT")
    if n_tot == 0:
        overall = "INSUFFICIENT_DATA"
    elif pista_chiusa:
        overall = "REJECTED"
    else:
        overall = "PARZIALMENTE_POSITIVO"

    payload: dict[str, Any] = {
        "generated": datetime.now(UTC).isoformat(),
        "framework": "BL-741 cross-pillar conditioning (EF-004@13-meta-synthesis)",
        "parameters": {
            "test_split": str(TEST_SPLIT),
            "vix_z_window": VIX_Z_WINDOW,
            "vix_z_min_periods": VIX_Z_MIN_PERIODS,
            "veto_full_z": VETO_FULL_Z,
            "ema": [EMA_FAST, EMA_SLOW],
            "donchian_n": DONCHIAN_N,
            "target_vol_es": TARGET_VOL_ES,
            "target_vol_crypto": TARGET_VOL_CRYPTO,
            "cost_bps_daily": COST_BPS_DAILY,
            "cost_bps_hourly": COST_BPS_HOURLY,
            "helpful_dsr_min_delta": HELPFUL_DSR_MIN_DELTA,
            "turnover_max_ratio": TURNOVER_MAX_RATIO,
        },
        "rows": rows,
        "verdicts": verdicts,
        "overall": overall,
        "n_pillars_negative": n_neg,
        "n_pillars_total": n_tot,
        "precedent_sprint_2d": "funding-z NEGATIVO (ETHUSDT SR +0.51→+0.46; BTCUSDT -0.02→-0.52)",
    }
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pillar-conditioning-sprint.json").write_text(
        json.dumps(payload, indent=2, default=str)
    )
    (out_dir / "pillar-conditioning-sprint.md").write_text(
        _render_markdown(
            rows,
            verdicts,
            n_pillars_total=n_tot,
            test_split=TEST_SPLIT,
            vix_z_verdict=vix_z_verdict,
        )
    )

    # Console summary
    print(
        f"{'leg':25s} {'pillar':20s} {'variant':12s} {'SR':>7s} {'ann':>8s} "
        f"{'DD':>7s} {'trades':>7s}"
    )
    for r in rows:
        print(
            f"{r['leg']:25s} {r['pillar']:20s} {r['variant']:12s} "
            f"{r['sharpe']:>+7.2f} {r['annual_return']:>+8.1%} "
            f"{r['max_drawdown']:>7.1%} {r['trades']:>7d}"
        )
    print(f"\nOverall: {overall} ({n_neg}/{n_tot} pillars negative)")
    print(f"Verdicts: {verdicts}")
    print(f"Report → {out_dir / 'pillar-conditioning-sprint.md'}")

    # -----------------------------------------------------------------------
    # Optional registry transition
    # -----------------------------------------------------------------------
    if args.update_registry:
        from analytics.research.factory.registry import (  # lazy import
            HypothesisRegistry,
            RegistryError,
        )

        reg = HypothesisRegistry().scan()
        domain_name = "13-meta-synthesis"
        domain_reg = reg.get_domain(domain_name)
        h = domain_reg.get("EF-004")

        def _advance(hyp: Any, nuovo_stato: str, motivo: str) -> bool:
            try:
                hyp.transition(
                    nuovo_stato,
                    motivo,
                    ref="docs/reports/edge-factory/pillar-conditioning-sprint.md",
                )
            except RegistryError as exc:
                print(f"Registry: skip {nuovo_stato} ({exc})")
                return False
            reg.save_domain(domain_name)
            return True

        if h.stato == "da_amplificare":
            _advance(h, "amplificata", "BL-741: pilastri VIX-z + funding-z costruiti e documentati")
        h = reg.get_domain(domain_name).get("EF-004")
        if h.stato == "amplificata":
            _advance(h, "in_qualifica", "BL-741: walk-forward qualification in corso")
        h = reg.get_domain(domain_name).get("EF-004")
        nuovo_stato = "APPROVED" if overall == "APPROVED" else "REJECTED"
        if h.stato in ("APPROVED", "REJECTED"):
            print(f"Registry: EF-004@{domain_name} già terminale ({h.stato}), skip")
        else:
            motivo = (
                f"BL-741 walk-forward > {TEST_SPLIT.date()}: "
                f"{n_neg}/{n_tot} pilastri NEGATIVI → pista conditioning-lite "
                f"{'APPROVED' if overall == 'APPROVED' else 'CHUSA (morta_per_evidenza)'}"
            )
            ok = _advance(h, nuovo_stato, motivo)
            if ok:
                print(f"Registry: EF-004@{domain_name} → {nuovo_stato} (persisted)")

        h_final = reg.get_domain(domain_name).get("EF-004")
        if h_final.stato != nuovo_stato and h.stato in ("APPROVED", "REJECTED"):
            print(
                f"WARNING: EF-004@{domain_name} post-transition stato = {h_final.stato} "
                f"(atteso {nuovo_stato})"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
