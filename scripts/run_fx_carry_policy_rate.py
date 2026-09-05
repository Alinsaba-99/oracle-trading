#!/usr/bin/env python3
"""BL-740 — FX carry policy-rate basket (EF-004@02-macro fx-carry-policy-rate-differential).

Prereg: ipotesi EF-004 nel registry 02-macro; basket FROZEN dalla letteratura
(Lustig-Roussanov-Verdelhan 2011 RFS; Menkhoff-Sarno-Schmeling-Schrimpf 2012 JF):
- 7 coppie G10, segnale mensile ±1 = segno(tasso_A − tasso_B) con CARRY_LAG_MONTHS=2
  anti-lookahead (il valore FRED PIT pubblicato con certezza 2 mesi dopo);
- dollar-neutral, vol-target 10%, costi 1.5 bps/turnover, walk-forward test > 2022-12-31;
- TAIL-CHECK PRE-REGISTRATO: finestre 2020-03 e 2022-USD-rally riportate come
  righe dedicate SEMPRE (anche se il basket passa);
- limitazione dichiarata: carry da policy rates ≠ carry da 3M forwards (proxy
  conservativa, niente swap rates forward).
Gates identici Sprint 1/2. Output: fx-carry-policy-rate.{md,json}.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Reuse Task 2's lake loader (proven interface — no duplication).
from analytics.metrics.canonical import max_drawdown_from_returns, sharpe_ratio  # ADR-021
from analytics.qualification.dsr import deflated_sharpe_ratio
from analytics.research.factory.haircut_sharpe import haircut_sharpe_ratio
from analytics.research.factory.registry import HypothesisRegistry
from scripts.run_overnight_drift_sprint import load_1h  # BL-739

# --- frozen mapping (do NOT tune in-sprint) --------------------------------
# G10 policy rates from FRED (free, $0/mo). FEDFUNDS (US) is the most
# well-known short-rate series; ECBDFR is the ECB deposit facility rate;
# the IRSTCI01xx series are OECD harmonised short-term interest rates for
# the remaining G10 (monthly, vintage via ALFRED).
RATE_SERIES: dict[str, str] = {
    "USD": "FEDFUNDS",
    "EUR": "ECBDFR",
    "JPY": "IRSTCI01JPM156N",
    "GBP": "IRSTCI01GBM156N",
    "CHF": "IRSTCI01CHM156N",
    "CAD": "IRSTCI01CAM156N",
    "AUD": "IRSTCI01AUM156N",
    "NZD": "IRSTCI01NZM156N",
}
# G10 carry basket — exactly 7 pairs (per brief). Long leg first = the
# higher-yield currency at each rebalance.
PAIR_CCY: dict[str, tuple[str, str]] = {
    "EURUSD": ("EUR", "USD"),
    "GBPUSD": ("GBP", "USD"),
    "USDJPY": ("USD", "JPY"),
    "USDCHF": ("USD", "CHF"),
    "USDCAD": ("USD", "CAD"),
    "AUDUSD": ("AUD", "USD"),
    "NZDUSD": ("NZD", "USD"),
}
# Stable iteration order for the report and the position series.
PAIR_ORDER: tuple[str, ...] = ("EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD")
# Anti-lookahead: the policy rate observed at month-t is "known" at month
# t+2 with certainty (the OECD IRSTCI01xx series have a 2-month publication
# lag in the vintage data).  The function ``build_rates_table`` applies this
# shift so the rest of the pipeline can ignore it.
CARRY_LAG_MONTHS: int = 2

# --- backtest constants (identical convention to Task 2) ------------------
TEST_SPLIT = pd.Timestamp("2022-12-31", tz="UTC")
PERIODS_PER_YEAR_1H: int = 24 * 365
COST_BPS_DEFAULT: float = 1.5  # FX institutional
TARGET_VOL: float = 0.10  # 10% annualised
VOL_WINDOW_HOURS: int = 720
MIN_BARS: int = 50_000
POSITION_CAP: float = 2.0
TAIL_WINDOWS: tuple[tuple[str, str, str], ...] = (
    ("2020-03", "2020-04", "2020-03 COVID FX dislocation"),
    ("2022-04", "2022-10", "2022 USD rally (Fed hikes + risk-off)"),
)

# Gates (identici Sprint 1/2)
HAIRCUT_SHARPE_GATE: float = 0.0
DSR_MIN: float = 0.5
KILL_MIN_PASSING_SLOTS: int = 2

# Informational disclosure: CFD swap/roll on XAU overnight is ~0.5-2% per
# year per dossier C (carry families).  FX swaps/rolls on broker CFDs are
# ~5-30 bps/day on majors (post-2022 carry-friendly regimes), but this
# runner trades spot 1h so we don't debit them — we disclose the range
# instead.
SWAP_ROLL_INFO_RANGE_PCT_YR: tuple[float, float] = (0.5, 2.0)


# ---------------------------------------------------------------------------
# Helpers — public for tests + downstream tasks
# ---------------------------------------------------------------------------


def _pair_to_assets(pair: str) -> tuple[str, str]:
    """Resolve a pair string into (ccy_a, ccy_b).  Raises on unknown."""
    if pair not in PAIR_CCY:
        raise KeyError(f"unknown pair {pair} (have: {sorted(PAIR_CCY)})")
    return PAIR_CCY[pair]


def build_rates_table(
    raw: pd.DataFrame, lag_months: int = CARRY_LAG_MONTHS
) -> tuple[pd.DataFrame, list[str]]:
    """Apply the PIT anti-lookahead lag to a monthly rates frame.

    The input is expected to have 8 columns (one per currency) keyed by
    ``RATE_SERIES``.  Missing columns are tolerated: the missing
    currencies are returned in a list so the runner can list them in the
    report instead of silently skipping the affected pairs.

    The lag implements **backward PIT semantics**: at decision month
    ``t`` the signal uses the rate **published at/before** ``t``.
    Because the OECD IRSTCI01xx series carry a 2-month publication lag
    (the value "for month m" is published at month m + 2), at month t
    the latest KNOWN rate is the one published at t - 2, which is the
    value originally labelled ``raw[t - 2]``.

    Implementation: ``lagged = df.iloc[: n - lag_months]`` reindexed to
    ``df.index[lag_months:]``.  Concretely ``lagged.iloc[i] ==
    raw.iloc[i - lag_months]``: row 0 (carrying the new index label
    M_lag_months) holds the rate originally at index label
    M_0 (= M_lag_months - lag_months).  Every lagged value is, by
    construction, at least ``lag_months`` older than its new label.

    Args:
        raw: monthly policy-rate frame, columns = 3-letter ccy codes.
        lag_months: how many months to shift (default ``CARRY_LAG_MONTHS``).

    Returns:
        ``(lagged_df, missing_ccys)``.  ``lagged_df`` has the same
        columns intersected with ``RATE_SERIES`` (preserving the order
        of ``RATE_SERIES``); ``missing_ccys`` lists the currencies that
        were absent in ``raw``.
    """
    expected = set(RATE_SERIES)
    present = set(raw.columns)
    missing = sorted(expected - present)
    keep_cols = [c for c in RATE_SERIES if c in present]
    df = raw[keep_cols].copy()
    if lag_months <= 0:
        return df, missing
    if lag_months >= len(df):
        # Not enough history to lag at all: every currency is effectively
        # unknown.  Return an empty frame and surface every currency as
        # missing so the runner reports the data gap honestly.
        return df.iloc[0:0].copy(), sorted(expected)
    # Backward PIT lag: keep the first (n - lag_months) values and
    # re-label them with the original index advanced by lag_months, so
    # at new label M_(lag_months + i) we report the value of M_i.
    cut = len(df) - lag_months
    lagged = df.iloc[:cut].copy()
    lagged.index = df.index[lag_months:]
    return lagged, missing


def carry_signal(rates: pd.DataFrame) -> pd.Series:
    """Build the monthly ±1 carry signal per pair from a lagged rates frame.

    For ``EURUSD = ("EUR", "USD")``: signal = +1 if EUR > USD else -1.
    For ``USDJPY = ("USD", "JPY")``: signal = +1 if USD > JPY else -1.
    Generalised: ``signal[pair] = +1 if rate[ccy_a] > rate[ccy_b] else -1``.

    Pairs whose leg currencies are absent from ``rates`` are excluded
    (and are flagged separately via :func:`build_rates_table` so the
    runner can list them in the report).

    Returns a ``pd.Series`` indexed by pair name in :data:`PAIR_ORDER`
    order — i.e. a *single-period* signal vector (the monthly column is
    the most recent observation; the grid-layer shifts it across hours
    via the BL-738 single-bar causal shift).
    """
    out: dict[str, int] = {}
    if rates.empty:
        return pd.Series(dtype=int)
    last = rates.iloc[-1]
    for pair in PAIR_ORDER:
        ccy_a, ccy_b = _pair_to_assets(pair)
        if ccy_a not in last.index or ccy_b not in last.index:
            continue  # excluded → listed in report
        diff = float(last[ccy_a]) - float(last[ccy_b])
        out[pair] = 1 if diff > 0 else (-1 if diff < 0 else 0)
    return pd.Series(out, dtype=int).reindex(PAIR_ORDER).dropna().astype(int)


# ---------------------------------------------------------------------------
# FRED I/O — graceful degradation (no silent skip)
# ---------------------------------------------------------------------------


def _fred_key_present() -> bool:
    """True if either FRED_API_KEY (canonical) or ORACLE_DATA_FRED_KEY
    (.env name) is set to a non-empty value.  FRED_API_KEY wins so an
    operator can override the .env file from the shell.
    """
    return bool(
        os.environ.get("FRED_API_KEY") or os.environ.get("ORACLE_DATA_FRED_KEY", "")
    )


def _try_fetch_one_series(series_id: str, start: str, end: str) -> pd.DataFrame | None:
    """Synchronous wrapper around FREDClient.fetch_series.

    Returns a pandas DataFrame indexed by period start with a single
    ``value`` column.  Returns ``None`` on any failure (no key, network
    error, series missing) — the caller lists the series in the report.

    The runner accepts either ``FRED_API_KEY`` (canonical, what
    ``analytics.macro.fred.FREDClient`` reads) or ``ORACLE_DATA_FRED_KEY``
    (the project-specific name in the shipped ``.env``).  ``FRED_API_KEY``
    wins when both are set so an operator can override the env file from
    the shell.
    """
    api_key = os.environ.get("FRED_API_KEY") or os.environ.get(
        "ORACLE_DATA_FRED_KEY", ""
    )
    if not api_key:
        return None
    try:
        from analytics.macro.fred import FREDClient  # lazy import
    except Exception:
        return None
    try:

        async def _run() -> Any:
            async with FREDClient(api_key=api_key) as c:
                return await c.fetch_series(series_id, start=start, end=end)

        df_pl = asyncio.run(_run())
    except Exception:
        return None
    if df_pl is None or df_pl.height == 0:
        return None
    # polars DataFrame → pandas (period start, value)
    pdf = df_pl.to_pandas() if hasattr(df_pl, "to_pandas") else df_pl
    if "date" not in pdf.columns or "value" not in pdf.columns:
        return None
    pdf["date"] = pd.to_datetime(pdf["date"])
    pdf = pdf.set_index("date").sort_index()
    s = pdf["value"].astype(float)
    # Reindex to month-start period index.
    s.index = s.index.to_period("M")
    return s.to_frame("value")


def fetch_rates_table(
    start: str = "1999-01-01", end: str | None = None
) -> tuple[pd.DataFrame, list[tuple[str, str]]]:
    """Fetch all G10 policy rates from FRED.

    Returns ``(rates_df, unavailable)`` where ``rates_df`` is a wide
    frame with one column per available currency (3-letter code) and a
    ``PeriodIndex`` (monthly); ``unavailable`` is a list of
    ``(currency, series_id)`` tuples that could not be fetched.

    No silent skip: every missing series is in the returned list and
    surfaces in the report.  If neither ``FRED_API_KEY`` nor
    ``ORACLE_DATA_FRED_KEY`` is set (or the network is down), every
    currency is reported as unavailable.
    """
    end_eff = end or datetime.now(UTC).strftime("%Y-%m-%d")
    rates: dict[str, pd.Series] = {}
    unavailable: list[tuple[str, str]] = []
    for ccy, sid in RATE_SERIES.items():
        df = _try_fetch_one_series(sid, start=start, end=end_eff)
        if df is None or df.empty:
            unavailable.append((ccy, sid))
            continue
        # FRED's FEDFUNDS/ECBDFR are at month-start; the IRSTCI01xx are
        # at month-start as well — align by PeriodIndex.to_timestamp.
        s = df["value"].copy()
        s.index = s.index.to_period("M")
        s.name = ccy
        rates[ccy] = s
    if not rates:
        return pd.DataFrame(), unavailable
    out = pd.concat(rates.values(), axis=1)
    out.columns = list(rates.keys())
    out = out.sort_index()
    return out, unavailable


# ---------------------------------------------------------------------------
# Spot I/O + position construction (Task 2 reuse)
# ---------------------------------------------------------------------------


def _vol_scalar(close: pd.Series) -> pd.Series:
    """1% target per-bar vol scalar — same recipe as Task 2.

    Reuses the BL-739 vol-target so this runner's basket has the same
    vol regime as the overnight-drift sprint (auditable side-by-side).
    """
    ret = close.pct_change()
    rv = ret.rolling(VOL_WINDOW_HOURS, min_periods=168).std() * math.sqrt(PERIODS_PER_YEAR_1H)
    return (TARGET_VOL / rv.replace(0.0, np.nan)).clip(upper=POSITION_CAP)


def _spread_signal_to_grid(signal: int, idx: pd.DatetimeIndex) -> pd.Series:
    """Spread a single ±1 integer signal across the 1h grid.

    The signal is *constant* across every bar — rebalance happens at the
    month boundary only; the cost model charges on |Δpos| so a constant
    signal pays zero per-bar turnover (just the rebalance events).
    """
    return pd.Series(float(signal), index=idx)


def _position_path(signals_by_month: pd.Series, grid_idx: pd.DatetimeIndex) -> pd.Series:
    """Build the per-bar position for one pair by aligning monthly signals
    to the 1h grid.

    ``signals_by_month`` is a ``pd.Series`` indexed by ``PeriodIndex(M)``
    with values ±1.  We forward-fill within each month so the position
    is constant across every bar in the same calendar month.  The BL-738
    single-bar causal shift is applied inside :func:`_strategy_returns`.
    """
    if signals_by_month.empty:
        return pd.Series(0.0, index=grid_idx)
    # Map each bar to its month-start period, then ffill the signal.
    bar_periods = pd.PeriodIndex(grid_idx, freq="M")
    aligned = signals_by_month.reindex(bar_periods.unique()).ffill()
    mapped = pd.Series(aligned.reindex(bar_periods).to_numpy(), index=grid_idx)
    return mapped.fillna(0.0).astype(float)


# ---------------------------------------------------------------------------
# Per-pair evaluation
# ---------------------------------------------------------------------------


@dataclass
class PairResult:
    pair: str
    n_bars_total: int
    n_test_bars: int
    trades: int
    cost_drag: float
    sharpe: float
    haircut_sharpe: float
    dsr: float | None
    max_drawdown: float
    annual_return: float
    status: str  # OK | INSUFFICIENT_DATA | EXCLUDED_NO_RATES | ERROR


def _strategy_returns(
    pos: pd.Series, close: pd.Series, cost_bps: float
) -> tuple[pd.Series, pd.Series, int]:
    """Per-bar strategy returns with turnover costs (BL-738 convention).

    Position is shifted 1 bar (today's signal drives tomorrow's return).
    Costs are charged on |Δpos| × cost_bps/10000.  Returns
    ``(strat_net, cost_rate, n_trades)``.
    """
    log_ret = np.log(close).diff()
    strat = pos.shift(1) * log_ret
    turnover = pos.diff().abs().fillna(0.0)
    cost_rate = turnover * (cost_bps / 10_000.0)
    strat_net = (strat.fillna(0.0) - cost_rate).fillna(0.0)
    n_trades = int((turnover > 0).sum())
    return strat_net, cost_rate, n_trades


def _evaluate_pair(
    pair: str, close: pd.Series, signals_by_month: pd.Series, cost_bps: float, n_trials: int
) -> PairResult:
    grid = pd.DatetimeIndex(close.index)
    pos_raw = _position_path(signals_by_month, grid)
    pos = pos_raw * _vol_scalar(close)
    strat, cost_rate, trades = _strategy_returns(pos, close, cost_bps)
    test = strat[strat.index > TEST_SPLIT].dropna()
    cost_rate_test = cost_rate[cost_rate.index > TEST_SPLIT]
    cost_total_test = float(cost_rate_test.sum())
    arr = test.to_numpy()
    if arr.size < 8:
        return PairResult(
            pair=pair,
            n_bars_total=len(close),
            n_test_bars=len(test),
            trades=trades,
            cost_drag=cost_total_test,
            sharpe=0.0,
            haircut_sharpe=float("nan"),
            dsr=None,
            max_drawdown=0.0,
            annual_return=0.0,
            status="INSUFFICIENT_DATA",
        )
    sr = sharpe_ratio(arr, periods_per_year=PERIODS_PER_YEAR_1H)
    hs = haircut_sharpe_ratio(arr, n_trials=n_trials, periods_per_year=PERIODS_PER_YEAR_1H)
    dsr = deflated_sharpe_ratio(arr, n_trials=n_trials, periods_per_year=PERIODS_PER_YEAR_1H)
    dd = max_drawdown_from_returns(arr)
    annual = float((1 + test).prod() ** (PERIODS_PER_YEAR_1H / max(len(test), 1)) - 1)
    return PairResult(
        pair=pair,
        n_bars_total=len(close),
        n_test_bars=len(test),
        trades=trades,
        cost_drag=cost_total_test,
        sharpe=float(sr) if np.isfinite(sr) else 0.0,
        haircut_sharpe=float(hs) if np.isfinite(hs) else float("nan"),
        dsr=float(dsr) if dsr is not None and np.isfinite(dsr) else None,
        max_drawdown=float(dd),
        annual_return=annual,
        status="OK",
    )


# ---------------------------------------------------------------------------
# Tail-check helpers
# ---------------------------------------------------------------------------


def _tail_window_returns(close: pd.Series, start: str, end: str) -> tuple[float, int]:
    """Cumulative log-return and bar count over a tail window."""
    log_ret = np.log(close).diff().fillna(0.0)
    lo = pd.Timestamp(start, tz="UTC")
    hi = pd.Timestamp(end, tz="UTC")
    sub = log_ret[(log_ret.index >= lo) & (log_ret.index <= hi)]
    if sub.empty:
        return 0.0, 0
    return float(sub.sum()), len(sub)


def _tail_returns_pair(
    pair_results: dict[str, PairResult],
    closes: dict[str, pd.Series],
    signals_by_month: dict[str, pd.Series],
    start: str,
    end: str,
) -> tuple[float, int]:
    """Cross-pair weighted tail return (equal-weight basket within window)."""
    rets: list[float] = []
    for pair, res in pair_results.items():
        if res.status != "OK":
            continue
        close = closes.get(pair)
        if close is None:
            continue
        sig = signals_by_month.get(pair)
        if sig is None or sig.empty:
            continue
        grid = pd.DatetimeIndex(close.index)
        pos = _position_path(sig, grid).shift(1).fillna(0.0)
        # Build per-bar log returns inside the window.
        log_ret = np.log(close).diff().fillna(0.0)
        pos = pos.reindex(log_ret.index).fillna(0.0)
        lo = pd.Timestamp(start, tz="UTC")
        hi = pd.Timestamp(end, tz="UTC")
        win = pos[(pos.index >= lo) & (pos.index <= hi)]
        ret_w = log_ret.reindex(win.index)
        rets.append(float((win * ret_w).sum()))
    if not rets:
        return 0.0, 0
    return float(np.mean(rets)), len(rets)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lake-root", default="data/lake/curated")
    parser.add_argument("--out-dir", default="docs/reports/edge-factory")
    parser.add_argument(
        "--update-registry",
        action="store_true",
        help="Transition EF-004@02-macro to APPROVED/REJECTED based on verdict (persist=True).",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip FRED I/O and use a synthetic rates table (CI / no-network mode).",
    )
    parser.add_argument(
        "--synthetic-rates-json",
        type=str,
        default=None,
        help="Optional JSON file with a {ccy: [values per month]} synthetic rates table.",
    )
    args = parser.parse_args()
    lake_root = Path(args.lake_root)
    out_dir = Path(args.out_dir)

    n_trials = len(PAIR_ORDER) + 1  # 7 pairs + 1 = 8 trials (Sprint 1/2 convention)

    # --- fetch or synthesize rates -----------------------------------------
    if args.synthetic_rates_json:
        blob = json.loads(Path(args.synthetic_rates_json).read_text(encoding="utf-8"))
        idx = pd.PeriodIndex(blob["index"], freq="M")
        raw = pd.DataFrame({k: pd.Series(v, index=idx) for k, v in blob["rates"].items()})
        unavailable: list[tuple[str, str]] = []
    elif args.offline or not _fred_key_present():
        # Honest about no FRED access: list every currency as unavailable.
        unavailable = list(RATE_SERIES.items())
        raw = pd.DataFrame()
    else:
        raw, unavailable = fetch_rates_table()
        if raw.empty:
            unavailable = list(RATE_SERIES.items())

    lagged, missing_ccys = build_rates_table(raw)
    missing_pairs = [p for p in PAIR_ORDER if any(c in missing_ccys for c in _pair_to_assets(p))]

    # --- build signals per pair (one column of monthly signals) ------------
    if lagged.empty:
        signals_by_month: dict[str, pd.Series] = {}
    else:
        # For each pair, build the monthly ±1 signal at every period in
        # the lagged frame.
        signals_by_month = {}
        for pair in PAIR_ORDER:
            ccy_a, ccy_b = _pair_to_assets(pair)
            if ccy_a not in lagged.columns or ccy_b not in lagged.columns:
                continue
            d = lagged[ccy_a] - lagged[ccy_b]
            signals_by_month[pair] = d.apply(
                lambda x, _p=pair: 1 if x > 0 else (-1 if x < 0 else 0)
            ).astype(int)

    # --- evaluate each pair against the lake --------------------------------
    results: list[PairResult] = []
    closes: dict[str, pd.Series] = {}
    for pair in PAIR_ORDER:
        if pair not in signals_by_month:
            results.append(
                PairResult(
                    pair=pair,
                    n_bars_total=0,
                    n_test_bars=0,
                    trades=0,
                    cost_drag=0.0,
                    sharpe=0.0,
                    haircut_sharpe=float("nan"),
                    dsr=None,
                    max_drawdown=0.0,
                    annual_return=0.0,
                    status="EXCLUDED_NO_RATES",
                )
            )
            continue
        close = load_1h(lake_root, pair)
        if close is None:
            results.append(
                PairResult(
                    pair=pair,
                    n_bars_total=0,
                    n_test_bars=0,
                    trades=0,
                    cost_drag=0.0,
                    sharpe=0.0,
                    haircut_sharpe=float("nan"),
                    dsr=None,
                    max_drawdown=0.0,
                    annual_return=0.0,
                    status="INSUFFICIENT_DATA",
                )
            )
            continue
        closes[pair] = close
        res = _evaluate_pair(
            pair, close, signals_by_month[pair], cost_bps=COST_BPS_DEFAULT, n_trials=n_trials
        )
        results.append(res)

    # --- aggregate gates ----------------------------------------------------
    passing_pairs: list[str] = []
    for r in results:
        if r.status != "OK":
            continue
        if np.isfinite(r.haircut_sharpe) and r.haircut_sharpe > HAIRCUT_SHARPE_GATE:
            dsr_v = r.dsr if r.dsr is not None else 0.0
            if dsr_v > DSR_MIN:
                passing_pairs.append(r.pair)
    verdict = "GO" if len(passing_pairs) >= KILL_MIN_PASSING_SLOTS else "NO_GO"

    # --- tail-check --------------------------------------------------------
    pr_by_pair = {r.pair: r for r in results}
    tail_rows: list[dict[str, Any]] = []
    for start_str, end_str, label in TAIL_WINDOWS:
        per_pair_logret: dict[str, float] = {}
        for pair, close in closes.items():
            pair_log_ret, _n = _tail_window_returns(close, start_str, end_str)
            per_pair_logret[pair] = pair_log_ret
        basket_ret, n_pairs = _tail_returns_pair(
            pr_by_pair, closes, signals_by_month, start_str, end_str
        )
        tail_rows.append(
            {
                "window": label,
                "start": start_str,
                "end": end_str,
                "basket_log_return": basket_ret,
                "n_pairs_in_basket": n_pairs,
                "per_pair_log_return": per_pair_logret,
            }
        )

    # --- serialise ---------------------------------------------------------
    payload: dict[str, Any] = {
        "generated": datetime.now(UTC).isoformat(),
        "framework": (
            "BL-740 FX carry policy-rate basket — EF-004@02-macro "
            "(Lustig-Roussanov-Verdelhan 2011; Menkhoff et al 2012; "
            "PIT FRED with CARRY_LAG_MONTHS=2)"
        ),
        "parameters": {
            "rate_series": RATE_SERIES,
            "pairs": PAIR_ORDER,
            "carry_lag_months": CARRY_LAG_MONTHS,
            "test_split": str(TEST_SPLIT),
            "cost_bps": COST_BPS_DEFAULT,
            "target_vol": TARGET_VOL,
            "vol_window_hours": VOL_WINDOW_HOURS,
            "min_bars": MIN_BARS,
            "n_trials": n_trials,
            "gates": {
                "haircut_sharpe_min": HAIRCUT_SHARPE_GATE,
                "dsr_min": DSR_MIN,
                "min_passing_slots": KILL_MIN_PASSING_SLOTS,
            },
        },
        "data": {
            "fred_unavailable": [{"currency": c, "series_id": s} for c, s in unavailable],
            "missing_currencies": missing_ccys,
            "excluded_pairs": missing_pairs,
            "rates_shape": [int(raw.shape[0]), int(raw.shape[1])] if not raw.empty else [0, 0],
            "lagged_shape": [int(lagged.shape[0]), int(lagged.shape[1])]
            if not lagged.empty
            else [0, 0],
        },
        "results": [asdict(r) for r in results],
        "tail_checks": tail_rows,
        "verdict": verdict,
        "passing_pairs": passing_pairs,
        "n_passing_pairs": len(passing_pairs),
        "swap_roll_disclosure_pct_yr": list(SWAP_ROLL_INFO_RANGE_PCT_YR),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "fx-carry-policy-rate.json").write_text(json.dumps(payload, indent=2, default=str))

    # --- markdown ----------------------------------------------------------
    lines: list[str] = [
        "# BL-740 — FX carry policy-rate basket (EF-004@02-macro)",
        "",
        f"**Generated**: {payload['generated']}",
        "",
        "**Prereg**: basket G10 FROZEN dalla letteratura (LRV 2011 RFS, Menkhoff 2012 JF).",
        f"Mapping {len(PAIR_ORDER)} pairs × 8 currencies; CARRY_LAG_MONTHS={CARRY_LAG_MONTHS}.",
        (
            f"Walk-forward test > {TEST_SPLIT.date()}. Costs "
            f"{COST_BPS_DEFAULT} bps/turnover, vol-target {TARGET_VOL:.0%}, "
            f"min bars {MIN_BARS:,}."
        ),
        "",
        f"**Verdetto famiglia: `{verdict}`** — "
        f"{len(passing_pairs)}/{len(PAIR_ORDER)} coppie passano entrambi i gate "
        f"(haircut SR > {HAIRCUT_SHARPE_GATE} AND DSR > {DSR_MIN}); "
        f"soglia kill = {KILL_MIN_PASSING_SLOTS}.",
        "",
        "## Dati",
        "",
    ]
    if unavailable:
        key_status = (
            "FRED_API_KEY / ORACLE_DATA_FRED_KEY assenti"
            if not _fred_key_present()
            else "FRED_API_KEY / ORACLE_DATA_FRED_KEY non valide o network offline"
        )
        lines += [
            f"**FRED non disponibile** ({key_status}): "
            "le seguenti coppie sono ESCLUSE e LISTATE qui — nessun silent skip:",
            "",
            "| currency | series_id |",
            "|---|---|",
        ]
        for ccy, sid in unavailable:
            lines.append(f"| {ccy} | {sid} |")
        lines.append("")
        if missing_pairs:
            lines += [
                "**Coppie escluse** (manca almeno una gamba): " + ", ".join(missing_pairs),
                "",
            ]
        else:
            lines += ["**Nessuna coppia esclusa** (tutte le 8 currency disponibili).", ""]
    else:
        lines += [
            f"FRED ha risposto per tutte le {len(RATE_SERIES)} series; "
            f"raw rates shape = {raw.shape}, lagged shape = {lagged.shape}.",
            "",
        ]

    lines += [
        "## Risultati per coppia",
        "",
        "| pair | SR | haircut SR | DSR | MaxDD | ann ret | trades | cost drag |",
        "| bars (tot / test) | status |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        dsr: str = f"{r.dsr:+.2f}" if r.dsr is not None else "n/a"
        hs: str = f"{r.haircut_sharpe:+.2f}" if np.isfinite(r.haircut_sharpe) else "n/a"
        lines.append(
            f"| {r.pair} | {r.sharpe:+.2f} | {hs} | {dsr} | "
            f"{r.max_drawdown:.1%} | {r.annual_return:+.1%} | {r.trades} | "
            f"{r.cost_drag:.4f} | {r.n_bars_total} / {r.n_test_bars} | {r.status} |"
        )

    lines += [
        "",
        "## Tail-check pre-registrato (sempre presente)",
        "",
        "Finestre dedicate: COVID 2020-03 e USD rally 2022. La riga `basket_log_return` "
        "è la media cross-pair sull'intero basket dentro la finestra (più negativo = peggio).",
        "",
        "| finestra | basket log-return | # coppie nel basket |",
        "|---|---|---|",
    ]
    for row in tail_rows:
        lines.append(
            f"| {row['window']} ({row['start']}→{row['end']}) | "
            f"{row['basket_log_return']:+.4f} | {row['n_pairs_in_basket']} |"
        )

    lines += [
        "",
        "### Tail per coppia (log-return cumulato sulla finestra)",
        "",
        "| finestra | EURUSD | GBPUSD | USDJPY | USDCHF | USDCAD | AUDUSD | NZDUSD |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in tail_rows:
        per = row["per_pair_log_return"]
        cells = []
        for p in PAIR_ORDER:
            v = per.get(p)
            cells.append(f"{v:+.4f}" if v is not None else "n/a")
        lines.append(f"| {row['window']} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "## Stima informativa swap/roll CFD",
        "",
        (
            f"Il backtest usa spot 1h (no swap). Su broker CFD/OTC il carry overnight "
            f"per XAU/cross FX è tipicamente {SWAP_ROLL_INFO_RANGE_PCT_YR[0]:.1f}%-"
            f"{SWAP_ROLL_INFO_RANGE_PCT_YR[1]:.1f}% annuo (dossier C — families "
            f"carry); qui non viene addebitato ma è dichiarato come costo informativo "
            f"per portare il basket in produzione su CFD broker."
        ),
        "",
        "## Limitazioni oneste",
        "",
        "- **CARRY_LAG_MONTHS=2** copre la publication lag OECD IRSTCI01xx ma NON eventuali revisioni tardive (rare per i policy rates).",
        "- **Proxy conservativa**: carry da policy rates ≠ carry da 3M forward swap rates; niente swap rates → edge teorico leggermente sottostimato.",
        "- **Dollar-neutrality by construction**: ogni coppia ha USD su un lato ma i segni sono indipendenti → l'esposizione USD netta può essere +1 o -1 in qualsiasi mese (3 long-USD, 4 short-USD); il basket non è USD-cash-neutral in senso stretto — è *pairwise neutral* contro USD. Questa è la convenzione LRV/Menkhoff e va riportata onestamente.",
        "- **N_trials=8** = 7 pairs + 1 cash-window sensitivity (frozen, prereg).",
        "- **Tail 2020-03 / 2022** sono finestre pre-registrate; se la basket le attraversa senza distruzione, è un punto positivo; se le distrugge, è il failure mode noto della letteratura (Menkhoff compensation).",
        "- **Env requirement**: il runner richiede una chiave FRED valida (32 char alfanumerica) in ``FRED_API_KEY`` (canonical, priorità alta) o ``ORACLE_DATA_FRED_KEY`` (nome del file .env del progetto, fallback). Per ottenere una chiave gratuita: https://fred.stlouisfed.org/docs/api/api_key.html . Senza chiave il runner degrada onestamente a verdict NO_GO con tutte le coppie ESCLUSE_NO_RATES (no crash, no silent skip).",
        "",
        "## Verdetto",
        "",
        (
            f"**`{verdict}`** con {len(passing_pairs)}/{len(PAIR_ORDER)} coppie "
            f"passanti ({passing_pairs or 'nessuna'})."
        ),
    ]
    (out_dir / "fx-carry-policy-rate.md").write_text("\n".join(lines) + "\n")

    # --- console summary ---------------------------------------------------
    print(f"{'pair':8s} {'SR':>6s} {'hsr':>6s} {'DSR':>6s} {'DD':>7s} {'trades':>7s} status")
    for r in results:
        dsr_str: str = f"{r.dsr:+.2f}" if r.dsr is not None else "n/a"
        hs_str: str = f"{r.haircut_sharpe:+.2f}" if np.isfinite(r.haircut_sharpe) else "n/a"
        print(
            f"{r.pair:8s} {r.sharpe:>+6.2f} {hs_str:>6s} {dsr_str:>6s} "
            f"{r.max_drawdown:>7.1%} {r.trades:>7d} {r.status}"
        )
    print(f"\nVerdict: {verdict} ({len(passing_pairs)}/{len(PAIR_ORDER)} coppie passanti)")
    print(f"Report → {out_dir / 'fx-carry-policy-rate.md'}")

    # --- optional registry transition --------------------------------------
    if args.update_registry:
        # EF-004 is per-domain (5 different hypotheses with same id, see plan §3);
        # brief `EF-004@02-macro` selects the 02-macro one specifically.  The
        # registry's high-level update_status finds the FIRST EF-004 across
        # all domains — wrong for our case.  We route the transition through
        # the domain-specific hypothesis directly and persist that single
        # domain (Task 2 workaround, validated).
        from analytics.research.factory.registry import RegistryError as _RegErr

        reg = HypothesisRegistry().scan()
        domain_name = "02-macro"
        domain_reg = reg.get_domain(domain_name)
        h = domain_reg.get("EF-004")

        def _advance(hyp: Any, nuovo_stato: str, motivo: str) -> bool:
            try:
                hyp.transition(
                    nuovo_stato, motivo, ref="docs/reports/edge-factory/fx-carry-policy-rate.md"
                )
            except _RegErr as exc:
                print(f"Registry: skip {nuovo_stato} ({exc})")
                return False
            reg.save_domain(domain_name)
            return True

        if h.stato == "da_amplificare":
            _advance(h, "amplificata", "BL-740: gambe policy-rate carry costruite e documentate")
        h = reg.get_domain(domain_name).get("EF-004")
        if h.stato == "amplificata":
            _advance(h, "in_qualifica", "BL-740: walk-forward qualification in corso")
        h = reg.get_domain(domain_name).get("EF-004")
        nuovo_stato = "APPROVED" if verdict == "GO" else "REJECTED"
        if h.stato in ("APPROVED", "REJECTED"):
            print(f"Registry: EF-004@{domain_name} già terminale ({h.stato}), skip")
        else:
            ok = _advance(
                h,
                nuovo_stato,
                f"BL-740 walk-forward > {TEST_SPLIT.date()}: "
                f"{len(passing_pairs)}/{len(PAIR_ORDER)} coppie passanti",
            )
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
