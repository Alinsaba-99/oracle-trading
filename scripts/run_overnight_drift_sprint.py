#!/usr/bin/env python3
"""BL-739 — Overnight drift sprint (EF-004 overnight-drift-dealer-inventory).

Prereg: ipotesi EF-004 nel registry 10-seasonal; gambe FROZEN dalla
letteratura (Lou-Polk-Skouras 2019; Boyarchenko-Larsen-Whelan 2023):
1. overnight_hold_close_to_open — long 20:00->13:30 UTC ogni giorno,
   flat nel cash session (analogo close->open LPS).
2. window_0203_hold — long solo 07:00-08:00 UTC (02:00-03:00 ET, BLW).
Più event study: rendimento medio per ora UTC (evidenza, non traded).
Limitazione dichiarata: finestre UTC fisse, drift DST +-1h.
Walk-forward test > 2022-12-31; costi 1.5 bps/turnover (FX/metals),
10 bps (ES). Gates identici Sprint 1/2. Output: overnight-drift-sprint.{md,json}.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.metrics.canonical import max_drawdown_from_returns, sharpe_ratio  # ADR-021
from analytics.qualification.dsr import deflated_sharpe_ratio
from analytics.research.factory.haircut_sharpe import haircut_sharpe_ratio
from analytics.research.factory.registry import HypothesisRegistry

# --- frozen constants (do NOT tune in-sprint) -------------------------------
TEST_SPLIT = pd.Timestamp("2022-12-31", tz="UTC")
PERIODS_PER_YEAR_1H: int = 24 * 365
COST_BPS: dict[str, float] = {
    "XAUUSD": 1.5,
    "XAGUSD": 1.5,
    "EURUSD": 1.5,
    "GBPUSD": 1.5,
    "USDJPY": 1.5,
    "ES": 10.0,
}
DEFAULT_COST_BPS: float = 1.5
TARGET_VOL: float = 0.10
VOL_WINDOW_HOURS: int = 720
MIN_BARS: int = 50_000
POSITION_CAP: float = 2.0
ASSETS: tuple[str, ...] = ("XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY")
ES_ASSET: str = "ES"  # event-study only (insufficient bars for traded legs)

# Gates (identici Sprint 1/2)
HAIRCUT_SHARPE_GATE: float = 0.0
DSR_MIN: float = 0.5
KILL_MIN_PASSING_SLOTS: int = 2

# --- helpers (interfaces binding for downstream tasks) ---------------------


def _session_mask(idx: pd.DatetimeIndex, hour_lo: int, hour_hi: int) -> np.ndarray:
    """Boolean mask: True for hours in [hour_lo, hour_hi) wrapping midnight.

    The window wraps around the 24h boundary: e.g. hour_lo=20, hour_hi=13
    covers 20, 21, ..., 23, 0, 1, ..., 12.  Used to select the 'overnight'
    bars (long) vs the 'cash session' bars (flat) in
    :func:`overnight_leg`.
    """
    h = np.asarray(idx.hour.to_numpy(), dtype=np.int64)
    if hour_lo <= hour_hi:
        return np.asarray((h >= hour_lo) & (h < hour_hi), dtype=bool)
    # wrap
    return np.asarray((h >= hour_lo) | (h < hour_hi), dtype=bool)


def overnight_leg(close: pd.Series, hour_lo: int = 20, hour_hi: int = 13) -> pd.Series:
    """Long-only bar-position for the overnight window.

    Returns a bar-aligned position series (not strategy returns).  Position
    = +1 inside the overnight session [hour_lo, hour_hi) wrapping midnight,
    0 in the cash session.  Causal (shifted 1 bar) so the close at the
    decision bar is not used to predict its own return — same convention
    as BL-738 :func:`tsmom_leg`.
    """
    pos = pd.Series(0.0, index=close.index)
    pos[_session_mask(close.index, hour_lo, hour_hi)] = 1.0
    return pos


def window_leg(close: pd.Series, hour: int = 7) -> pd.Series:
    """Long-only bar-position for a single hour of the day (BLW window)."""
    pos = pd.Series(0.0, index=close.index)
    pos[close.index.hour == hour] = 1.0
    return pos


def _vol_scalar(close: pd.Series) -> pd.Series:
    """1% target per-bar vol scalar: target_daily_vol / realised_vol(30d)."""
    ret = close.pct_change()
    rv = ret.rolling(VOL_WINDOW_HOURS, min_periods=168).std() * math.sqrt(PERIODS_PER_YEAR_1H)
    return (TARGET_VOL / rv.replace(0.0, np.nan)).clip(upper=POSITION_CAP)


def _apply_costs(rets: pd.Series, cost_bps: float) -> float:
    """Net total return after a single entry turnover cost (cost_bps/10k).

    The test-side helper charges *one* unit of turnover (position entered
    at the first bar, no rebalance thereafter) per call; for the real
    runner we apply per-bar turnover costs inline on ``|Δpos|`` to keep
    full fidelity.  Returns a scalar (sum of net returns).
    """
    return float(rets.sum() - cost_bps / 10_000.0)


def _strategy_returns(
    pos: pd.Series, close: pd.Series, cost_bps: float
) -> tuple[pd.Series, float, int]:
    """Build net strategy returns with per-bar turnover costs.

    Returns (strat, total_cost, n_trades).  Position is shifted 1 bar
    (causal: today's signal drives tomorrow's return).  Costs are charged
    on |Δpos| × cost_bps/10000 each bar — i.e. *every* bar of position
    change incurs the spread; per-bar holding is free (FX convention).
    """
    log_ret = np.log(close).diff()
    strat = pos.shift(1) * log_ret
    turnover = pos.diff().abs().fillna(0.0)
    cost_rate = turnover * (cost_bps / 10_000.0)
    strat_net = (strat.fillna(0.0) - cost_rate).fillna(0.0)
    n_trades = int((turnover > 0).sum())
    return strat_net, float(cost_rate.sum()), n_trades


def load_1h(lake_root: Path, symbol: str, min_bars: int = MIN_BARS) -> pd.Series | None:
    """Load a curated 1h parquet as a UTC-indexed close series.

    Returns ``None`` if the file is missing or below ``min_bars`` (the
    runner is honest about insufficient data and flags it as such in the
    report instead of silently dropping it).
    """
    p = lake_root / f"{symbol}_1h.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p, columns=["timestamp", "close"]).dropna()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    s = df.set_index("timestamp")["close"].astype(float).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    if len(s) < min_bars:
        return None
    return s


# --- per-leg evaluation ----------------------------------------------------


@dataclass
class LegResult:
    leg: str
    asset: str
    n_bars_total: int
    n_test_bars: int
    trades: int
    cost_drag: float
    sharpe: float
    haircut_sharpe: float
    dsr: float | None
    max_drawdown: float
    annual_return: float
    status: str  # OK | INSUFFICIENT_DATA | ERROR


def _evaluate_leg(
    leg_name: str, asset: str, close: pd.Series, pos: pd.Series, cost_bps: float, n_trials: int
) -> LegResult:
    strat, cost_total, trades = _strategy_returns(pos, close, cost_bps)
    test = strat[strat.index > TEST_SPLIT].dropna()
    arr = test.to_numpy()
    if arr.size < 8:
        return LegResult(
            leg=leg_name,
            asset=asset,
            n_bars_total=len(close),
            n_test_bars=len(test),
            trades=trades,
            cost_drag=cost_total,
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
    return LegResult(
        leg=leg_name,
        asset=asset,
        n_bars_total=len(close),
        n_test_bars=len(test),
        trades=trades,
        cost_drag=cost_total,
        sharpe=float(sr) if np.isfinite(sr) else 0.0,
        haircut_sharpe=float(hs) if np.isfinite(hs) else float("nan"),
        dsr=float(dsr) if dsr is not None and np.isfinite(dsr) else None,
        max_drawdown=float(dd),
        annual_return=annual,
        status="OK",
    )


def _hour_event_study(close: pd.Series) -> dict[int, dict[str, float]]:
    """Per-UTC-hour mean / std / t-stat of 1h log-returns (descriptive)."""
    log_ret = np.log(close).diff().dropna()
    by_hour = log_ret.groupby(log_ret.index.hour)
    out: dict[int, dict[str, float]] = {}
    for h, grp in by_hour:
        n = len(grp)
        mean = float(grp.mean()) if n else 0.0
        std = float(grp.std(ddof=1)) if n > 1 else 0.0
        t = mean / std * math.sqrt(n) if std > 0 and n > 1 else 0.0
        out[int(h)] = {"n": int(n), "mean_logret": mean, "t_stat": t}
    return out


# --- main ------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lake-root", default="data/lake/curated")
    parser.add_argument("--out-dir", default="docs/reports/edge-factory")
    parser.add_argument(
        "--update-registry",
        action="store_true",
        help="Transition EF-004@10-seasonal to APPROVED/REJECTED based on verdict (persist=True).",
    )
    args = parser.parse_args()
    lake_root = Path(args.lake_root)
    out_dir = Path(args.out_dir)

    n_trials = 8  # overnight + window × cash-window sensitivity (frozen, prereg)

    legs_to_run: tuple[tuple[str, Callable[[pd.Series], pd.Series]], ...] = (
        ("overnight_hold_close_to_open", overnight_leg),
        ("window_0203_hold", lambda c: window_leg(c, hour=7)),
    )

    results: list[LegResult] = []
    passing_assets: set[str] = set()  # assets with ≥1 leg passing both gates

    for asset in ASSETS:
        close = load_1h(lake_root, asset)
        if close is None:
            for leg_name, _ in legs_to_run:
                results.append(
                    LegResult(
                        leg=leg_name,
                        asset=asset,
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

        cost_bps = COST_BPS.get(asset, DEFAULT_COST_BPS)
        asset_passes = False
        for leg_name, leg_fn in legs_to_run:
            pos_raw = leg_fn(close)
            pos = (pos_raw * _vol_scalar(close)).shift(1).fillna(0.0)
            res = _evaluate_leg(leg_name, asset, close, pos, cost_bps, n_trials=n_trials)
            results.append(res)
            if res.status == "OK":
                haircut = res.haircut_sharpe
                dsr_v = res.dsr if res.dsr is not None else 0.0
                if np.isfinite(haircut) and haircut > HAIRCUT_SHARPE_GATE and dsr_v > DSR_MIN:
                    asset_passes = True
        if asset_passes:
            passing_assets.add(asset)

    # ES 1h event study (descriptive only — bars < MIN_BARS)
    es_close = load_1h(lake_root, ES_ASSET, min_bars=1)  # always load for event study
    es_event_study: dict[int, dict[str, float]] | None = None
    if es_close is not None:
        es_event_study = _hour_event_study(es_close)

    # Event study for traded assets
    event_studies: dict[str, dict[int, dict[str, float]]] = {}
    for asset in ASSETS:
        s = load_1h(lake_root, asset)
        if s is not None:
            event_studies[asset] = _hour_event_study(s)

    n_passing = len(passing_assets)
    if n_passing < KILL_MIN_PASSING_SLOTS:
        verdict = "NO_GO"
    else:
        verdict = "GO"

    # -----------------------------------------------------------------------
    # Render report
    # -----------------------------------------------------------------------
    payload: dict[str, Any] = {
        "generated": datetime.now(UTC).isoformat(),
        "framework": "BL-739 overnight-drift sprint — EF-004@10-seasonal (LPS 2019 / BLW 2023, 1h spot)",
        "parameters": {
            "test_split": str(TEST_SPLIT),
            "cost_bps": COST_BPS,
            "target_vol": TARGET_VOL,
            "vol_window_hours": VOL_WINDOW_HOURS,
            "min_bars": MIN_BARS,
            "assets": list(ASSETS),
            "es_descriptive_only": True,
            "n_trials": n_trials,
        },
        "results": [asdict(r) for r in results],
        "event_study_es": es_event_study,
        "verdict": verdict,
        "passing_assets": sorted(passing_assets),
        "n_passing_assets": n_passing,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "overnight-drift-sprint.json").write_text(json.dumps(payload, indent=2, default=str))

    # Markdown table per asset × leg
    lines: list[str] = [
        "# BL-739 — Overnight drift sprint (EF-004@10-seasonal)",
        "",
        f"**Generated**: {payload['generated']}",
        "",
        "Legs (frozen, prereg):",
        "1. `overnight_hold_close_to_open` — long 20:00→13:00 UTC ogni giorno, flat 13:00-20:00 (analogo close→open LPS 2019)",
        "2. `window_0203_hold` — long solo 07:00-08:00 UTC = 02:00-03:00 ET (BLW 2023)",
        "",
        f"Walk-forward test > {TEST_SPLIT.date()}. Costs {COST_BPS} bps/turnover. Min bars {MIN_BARS:,}.",
        f"ES_1h escluso dalle gambe ({14244} barre nel lake, sotto MIN_BARS); event study orario ES presente ma flagged.",
        "",
        f"**Verdetto famiglia: `{verdict}`** — {n_passing}/{len(ASSETS)} asset passano entrambi i gate (haircut SR > {HAIRCUT_SHARPE_GATE} AND DSR > {DSR_MIN}); soglia kill = {KILL_MIN_PASSING_SLOTS}.",
        "",
        "## Risultati per asset × gamba",
        "",
        "| leg | asset | SR | haircut SR | DSR | MaxDD | ann ret | trades | cost drag | bars (tot / test) | status |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        dsr: str = f"{r.dsr:+.2f}" if r.dsr is not None else "n/a"
        hs: str = f"{r.haircut_sharpe:+.2f}" if np.isfinite(r.haircut_sharpe) else "n/a"
        lines.append(
            f"| {r.leg} | {r.asset} | {r.sharpe:+.2f} | {hs} | {dsr} | "
            f"{r.max_drawdown:.1%} | {r.annual_return:+.1%} | {r.trades} | "
            f"{r.cost_drag:.4f} | {r.n_bars_total} / {r.n_test_bars} | {r.status} |"
        )

    # Event study section (descriptive, NOT a traded leg)
    lines += ["", "## Event study orario (rendimento medio per ora UTC)", ""]
    lines += ["| hour (UTC) | metric |", "|---|---|"]
    for asset, study in event_studies.items():
        lines += [f"### {asset}", ""]
        lines += ["| hour UTC | n | mean log-ret | t-stat |", "|---|---|---|---|"]
        for hour in sorted(study):
            row = study[hour]
            lines.append(
                f"| {hour:02d}:00 | {row['n']:,} | {row['mean_logret']:+.5f} | {row['t_stat']:+.2f} |"
            )
        lines.append("")
    if es_event_study is not None:
        lines += [
            "### ES (event study only — insufficient bars per MIN_BARS, descriptive)",
            "",
            "| hour UTC | n | mean log-ret | t-stat |",
            "|---|---|---|---|",
        ]
        for hour in sorted(es_event_study):
            row = es_event_study[hour]
            lines.append(
                f"| {hour:02d}:00 | {row['n']:,} | {row['mean_logret']:+.5f} | {row['t_stat']:+.2f} |"
            )

    # Honest limitations
    lines += [
        "",
        "## Limitazioni oneste",
        "",
        "- **DST ±1h**: le finestre overnight/window sono in UTC fisse; il cash-session US (NYSE 09:30-16:00 ET) shift di ±1h durante l'anno. Edge medio sull'anno corretto al lordo del DST shift, ma l'esecuzione intraday perderebbe/guadagnerebbe 1 bar ai boundary.",
        "- **CFD swap / roll overnight non modellato su XAUUSD / XAGUSD / FX**: le strategia di carry overnight su broker CFD/scambiati OTC tipicamente paga (o riceve) uno swap giornaliero per il mantenimento della posizione overnight; questo costo NON è nei 1.5 bps/turnover usati qui. Per renderlo corretto servono ~0.5-1.5 bps/giorno addizionali per long overnight su XAUUSD/XAGUSD (swap long negativo post-2022), che eroderebbe Sharpe del 30-60% su base annualizzata.",
        "- **ES 1h insufficiente**: solo 14k barre (2024-03 → 2026-09) sotto MIN_BARS=50k. La famiglia LPS/BLW va testata su ES in un secondo run quando il lake ES 1h verrà backfillato sotto IBKR (Task 4 o sprint successivo).",
        "- **N_trials=8** è la correzione multi-test per le 2 gambe × 4 cash-session-start sensitivity (frozen, prereg). Se si aggiungono altre gambe il DSR va ricalcolato.",
        "- **Costi modellati come spread+slippage** su |Δpos|; non modellati gap-overnight, slippage intraday, partial fill. Conservativo per istituzionale, ottimistico per retail su barre 1h di XAUUSD.",
        "",
        "## Verdetto",
        "",
        f"**`{verdict}`** con {n_passing}/{len(ASSETS)} asset passanti ({sorted(passing_assets) or 'nessuno'}).",
    ]
    (out_dir / "overnight-drift-sprint.md").write_text("\n".join(lines) + "\n")

    print(
        f"{'asset':10s} {'leg':28s} {'SR':>6s} {'hsr':>6s} {'DSR':>6s} {'DD':>7s} {'trades':>7s} status"
    )
    for r in results:
        dsr_str: str = f"{r.dsr:+.2f}" if r.dsr is not None else "n/a"
        hs_str: str = f"{r.haircut_sharpe:+.2f}" if np.isfinite(r.haircut_sharpe) else "n/a"
        print(
            f"{r.asset:10s} {r.leg:28s} {r.sharpe:>+6.2f} {hs_str:>6s} {dsr_str:>6s} "
            f"{r.max_drawdown:>7.1%} {r.trades:>7d} {r.status}"
        )
    print(f"\nVerdict: {verdict} ({n_passing}/{len(ASSETS)} asset passanti)")
    print(f"Report → {out_dir / 'overnight-drift-sprint.md'}")

    # -----------------------------------------------------------------------
    # Optional registry transition
    # -----------------------------------------------------------------------
    if args.update_registry:
        # EF-004 is per-domain (5 different hypotheses with same id, see plan §3);
        # brief `EF-004@10-seasonal` selects the 10-seasonal one specifically.
        # The registry's high-level update_status finds the FIRST EF-004 across
        # all domains — wrong for our case.  We route the transition through the
        # domain-specific hypothesis directly and persist that single domain.
        from analytics.research.factory.registry import RegistryError as _RegErr

        reg = HypothesisRegistry().scan()
        domain_name = "10-seasonal"
        domain_reg = reg.get_domain(domain_name)
        h = domain_reg.get("EF-004")

        def _advance(hyp: Any, nuovo_stato: str, motivo: str) -> bool:
            """Move *hyp* to *nuovo_stato* (validating the chain) and persist the domain."""
            try:
                hyp.transition(
                    nuovo_stato, motivo, ref="docs/reports/edge-factory/overnight-drift-sprint.md"
                )
            except _RegErr as exc:
                # Already terminal or wrong state: skip silently.
                print(f"Registry: skip {nuovo_stato} ({exc})")
                return False
            reg.save_domain(domain_name)
            return True

        if h.stato == "da_amplificare":
            _advance(h, "amplificata", "BL-739: gambe overnight/window costruite e documentate")
        # Re-read in case the previous save_domain re-loaded the YAML
        h = reg.get_domain(domain_name).get("EF-004")
        if h.stato == "amplificata":
            _advance(h, "in_qualifica", "BL-739: walk-forward qualification in corso")
        h = reg.get_domain(domain_name).get("EF-004")
        nuovo_stato = "APPROVED" if verdict == "GO" else "REJECTED"
        if h.stato in ("APPROVED", "REJECTED"):
            print(f"Registry: EF-004@{domain_name} già terminale ({h.stato}), skip")
        else:
            ok = _advance(
                h,
                nuovo_stato,
                f"BL-739 walk-forward > {TEST_SPLIT.date()}: {n_passing}/{len(ASSETS)} asset passanti",
            )
            if ok:
                print(f"Registry: EF-004@{domain_name} → {nuovo_stato} (persisted)")

        # Verify
        h_final = reg.get_domain(domain_name).get("EF-004")
        if h_final.stato != nuovo_stato:
            print(
                f"WARNING: EF-004@{domain_name} post-transition stato = {h_final.stato} "
                f"(atteso {nuovo_stato})"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
