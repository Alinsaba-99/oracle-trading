#!/usr/bin/env python3
"""BL-718 Sprint 2 — Qualification of real funding-rate factors (EF-001/EF-006).

Runs the pre-registered qualification gauntlet on the two funding-based
candidates from the crypto-microstructure registry, using **real**
Binance Vision funding data backfilled by ``scripts/backfill_funding_vision.py``:

1. **funding-extremum-reversal** (EF-001) — contrarian signal at
   funding z-score extremes: factor = − zscore(funding, 60d).  At an
   extreme positive z (crowded longs, expensive carry) the factor goes
   negative → expected negative forward return (short); at extreme
   negative z, factor positive → expected positive return (long).
2. **funding-z-ml-feature** (EF-006) — continuous, scale-free funding
   z-score as an unconditional directional factor: factor =
   − zscore(funding, 60d) evaluated at every bar (not just extremes),
   testing whether the normalised crowding level predicts returns
   monotonically across the whole distribution.

Data fusion (point-in-time safe):
    funding parquet (calc_time_ms → settlement timestamps, 8h grid) is
    forward-filled onto the OHLCV 1h grid with **shift(1)**: a bar can
    only use the funding rate settled at or before the bar open.  No
    lookahead.

Gauntlet: identical to Sprint 1 (BL-706 IC screen with 30% haircut +
moving-block bootstrap, BL-707 haircut Sharpe, ADR-017 DSR/PSR).  All
thresholds frozen; no overrides.

Outputs:
    docs/reports/edge-factory/sprint-2.md
    docs/reports/edge-factory/sprint-2.json

Usage:
    uv run --frozen python scripts/run_factory_sprint2_qualification.py
"""

from __future__ import annotations

import argparse
import json
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

from analytics.metrics.canonical import sharpe_ratio as canonical_sharpe  # ADR-021  # noqa: E402
from analytics.qualification.dsr import (  # ADR-017  # noqa: E402
    deflated_sharpe_ratio,
    probabilistic_sharpe_ratio,
)
from analytics.research.factory.haircut_sharpe import haircut_sharpe_ratio  # BL-707  # noqa: E402
from analytics.research.factory.ic_screen import screen_factor  # BL-706  # noqa: E402

# Frozen gauntlet thresholds — identical to Sprint 1 (BL-708).
ICIR_THRESHOLD: float = 0.05
IC_BLOCK_T_THRESHOLD: float = 2.5
IC_HAIRCUT_PCT: float = 30.0
HAIRCUT_SHARPE_GATE: float = 0.0
DSR_MIN: float = 0.5
PSR_MIN: float = 0.5
DEFAULT_HORIZON_HOURLY: int = 24
PERIODS_PER_YEAR_1H: int = 24 * 365
KILL_MIN_PASSING_SLOTS: int = 2
VERDICT_GO = "GO"
VERDICT_NO_GO = "NO_GO"
VERDICT_INSUFFICIENT = "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_funding_onto_prices(
    funding_dir: Path, lake_root: Path, asset: str
) -> tuple[pd.Series, pd.Series] | None:
    """Fuse funding settlements onto the 1h price grid (PIT-safe).

    Returns ``(close_1h, funding_on_grid)`` or None when either file is
    missing.  The funding rate settled at time T applies to bars in
    (T, T+8h]; we ffill the settlement value and shift(1) so a bar at
    open T only sees funding settled strictly before T.
    """
    fpath = funding_dir / f"{asset}.parquet"
    ppath = lake_root / f"{asset}_1h.parquet"
    if not fpath.exists() or not ppath.exists():
        return None
    fdf = pd.read_parquet(fpath)
    pdf = pd.read_parquet(ppath, columns=["timestamp", "close"]).dropna()
    pdf["timestamp"] = pd.to_datetime(pdf["timestamp"], utc=True)
    pdf = pdf.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    fidx = pd.to_datetime(fdf["calc_time_ms"].astype("int64") * 1_000_000, utc=True)
    fseries = pd.Series(
        fdf["funding_rate"].astype(float).to_numpy(), index=fidx, name="funding"
    ).sort_index()
    fseries = fseries[~fseries.index.duplicated(keep="last")]
    merged = pdf.set_index("timestamp")["close"].to_frame("close")
    merged["funding"] = (
        fseries.reindex(merged.index.union(fseries.index)).ffill().reindex(merged.index)
    )
    # PIT: bar at open T uses funding settled strictly before T
    merged["funding"] = merged["funding"].shift(1)
    merged = merged.dropna()
    if len(merged) < 500:
        return None
    return merged["close"], merged["funding"]


# ---------------------------------------------------------------------------
# Factors (frozen at sprint-time)
# ---------------------------------------------------------------------------


def funding_z(funding: pd.Series) -> pd.Series:
    """Rolling z-score of the funding rate over ~60 days (180 settlements)."""
    z = (funding - funding.rolling(180, min_periods=90).mean()) / funding.rolling(
        180, min_periods=90
    ).std(ddof=1).replace(0.0, np.nan)
    return z.rename("funding_z")


def extremum_reversal_factor(
    close: pd.Series, funding: pd.Series, horizon: int
) -> tuple[pd.Series, pd.Series]:
    """EF-001: contrarian at extremes — factor = −funding_z, gated |z| ≥ 2.

    Outside the gate the factor is 0 (no position); the IC screen sees
    the gated series (zero-inflated but honest: we only claim an edge
    at extremes).
    """
    z = funding_z(funding)
    factor = (-z).where(z.abs() >= 2.0, 0.0).rename("ef001")
    fwd = (close.shift(-horizon) / close - 1.0).rename("fwd_ret")
    return factor, fwd


def funding_z_factor(
    close: pd.Series, funding: pd.Series, horizon: int
) -> tuple[pd.Series, pd.Series]:
    """EF-006: continuous −z as unconditional directional factor."""
    z = funding_z(funding)
    factor = (-z).rename("ef006")
    fwd = (close.shift(-horizon) / close - 1.0).rename("fwd_ret")
    return factor, fwd


# ---------------------------------------------------------------------------
# Slot evaluation (reuses the Sprint 1 gauntlet verbatim)
# ---------------------------------------------------------------------------


@dataclass
class SlotResult:
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
    status: str


def _strategy_returns(factor: pd.Series, fwd: pd.Series) -> pd.Series:
    pair = pd.concat([factor.rename("f"), fwd.rename("r")], axis=1).dropna()
    if pair.empty:
        return pd.Series(dtype=float)
    return (np.sign(pair["f"]) * pair["r"]).rename("strategy")


def evaluate_slot(
    family: str,
    label: str,
    asset: str,
    factor: pd.Series,
    fwd: pd.Series,
    close: pd.Series,
    n_bars: int,
    horizon: int,
    boot_n: int,
) -> SlotResult:
    pair = pd.concat([factor.rename("f"), fwd.rename("r")], axis=1).dropna()
    close_on_pair_index = close.reindex(pair.index)
    n_pairs = int(pair.shape[0])
    if n_pairs < 200:
        return SlotResult(
            family=family,
            label=label,
            asset=asset,
            timeframe="1h",
            n_bars=n_bars,
            n_pairs=n_pairs,
            ic_passed=False,
            ic_mean=0.0,
            ic_std=0.0,
            icir_raw=0.0,
            icir_haircut=0.0,
            ic_t_block=0.0,
            observed_sharpe=0.0,
            haircut_sharpe=0.0,
            psr=None,
            dsr=None,
            status=VERDICT_INSUFFICIENT,
        )
    icr = screen_factor(
        factor=pair["f"],
        prices=close_on_pair_index,
        horizon=horizon,
        haircut_pct=IC_HAIRCUT_PCT,
        n_boot=boot_n,
    )
    strat = _strategy_returns(factor, fwd).dropna()
    if len(strat) < 2 or strat.std(ddof=1) == 0:
        obs_sr = 0.0
        hsr = 0.0
        psr = None
        dsr = None
    else:
        arr = strat.to_numpy()
        obs_sr = float(canonical_sharpe(arr, periods_per_year=PERIODS_PER_YEAR_1H))
        hsr = float(haircut_sharpe_ratio(arr, periods_per_year=PERIODS_PER_YEAR_1H))
        psr = float(probabilistic_sharpe_ratio(arr) or 0.0)
        dsr = float(
            deflated_sharpe_ratio(arr, n_trials=2, periods_per_year=PERIODS_PER_YEAR_1H) or 0.0
        )
    ic_passed = icr.icir_haircut > ICIR_THRESHOLD and icr.t_block > IC_BLOCK_T_THRESHOLD
    return SlotResult(
        family=family,
        label=label,
        asset=asset,
        timeframe="1h",
        n_bars=n_bars,
        n_pairs=n_pairs,
        ic_passed=bool(ic_passed),
        ic_mean=float(icr.ic_mean),
        ic_std=float(icr.ic_std),
        icir_raw=float(icr.icir),
        icir_haircut=float(icr.icir_haircut),
        ic_t_block=float(icr.t_block),
        observed_sharpe=obs_sr,
        haircut_sharpe=hsr,
        psr=psr,
        dsr=dsr,
        status="OK",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

FactorFn2 = Callable[[pd.Series, pd.Series, int], tuple[pd.Series, pd.Series]]


@dataclass(frozen=True)
class Sprint2Candidate:
    family: str
    label: str
    registry_id: str
    factor_fn: FactorFn2
    slots: tuple[tuple[str, str], ...]


CANDIDATES: list[Sprint2Candidate] = [
    Sprint2Candidate(
        family="funding_extremum_reversal",
        label="Funding Extremum Reversal",
        registry_id="crypto-microstructure/EF-001",
        factor_fn=extremum_reversal_factor,
        slots=(("BTCUSDT", "1h"), ("ETHUSDT", "1h"), ("SOLUSDT", "1h")),
    ),
    Sprint2Candidate(
        family="funding_z_feature",
        label="Funding Z (continuous)",
        registry_id="crypto-microstructure/EF-006",
        factor_fn=funding_z_factor,
        slots=(("BTCUSDT", "1h"), ("ETHUSDT", "1h"), ("SOLUSDT", "1h")),
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--funding-dir", default="data/lake/raw/funding")
    parser.add_argument("--lake-root", default="data/lake/curated")
    parser.add_argument("--out-dir", default="docs/reports/edge-factory")
    parser.add_argument("--boot-n", type=int, default=500)
    args = parser.parse_args()
    funding_dir = Path(args.funding_dir)
    lake_root = Path(args.lake_root)
    out_dir = Path(args.out_dir)

    all_slots: list[SlotResult] = []
    verdicts: dict[str, dict[str, object]] = {}
    for cand in CANDIDATES:
        slots = []
        for asset, tf in cand.slots:
            loaded = load_funding_onto_prices(funding_dir, lake_root, asset)
            if loaded is None:
                print(f"SKIP {asset} {tf}: data missing", file=sys.stderr)
                continue
            close, funding = loaded
            factor, fwd = cand.factor_fn(close, funding, DEFAULT_HORIZON_HOURLY)
            res = evaluate_slot(
                cand.family,
                cand.label,
                asset,
                factor,
                fwd,
                close,
                n_bars=int(close.size),
                horizon=DEFAULT_HORIZON_HOURLY,
                boot_n=args.boot_n,
            )
            slots.append(res)
            all_slots.append(res)
            print(
                f"{cand.family:30s} {asset:8s} IC={res.ic_mean:+.4f} "
                f"ICIRh={res.icir_haircut:+.4f} t={res.ic_t_block:+.2f} "
                f"pass={res.ic_passed} SRh={res.haircut_sharpe:+.2f} DSR={res.dsr}"
            )
        ok_slots = [s for s in slots if s.status == "OK"]
        ic_pass_n = sum(1 for s in ok_slots if s.ic_passed)
        med_hsr = float(np.median([s.haircut_sharpe for s in ok_slots])) if ok_slots else 0.0
        med_dsr = (
            float(np.median([s.dsr for s in ok_slots if s.dsr is not None])) if ok_slots else 0.0
        )
        reasons = []
        if ic_pass_n < KILL_MIN_PASSING_SLOTS:
            reasons.append(
                f"only {ic_pass_n} slots pass the IC screen "
                f"(kill criterion: >= {KILL_MIN_PASSING_SLOTS} required)"
            )
        if not ok_slots or med_hsr <= HAIRCUT_SHARPE_GATE:
            reasons.append(f"median haircut Sharpe {med_hsr:.4f} not > 0.0")
        if not ok_slots or med_dsr < DSR_MIN:
            reasons.append(f"median DSR {med_dsr:.4f} < 0.5 after deflated-SR penalty")
        verdict = VERDICT_GO if not reasons else VERDICT_NO_GO
        verdicts[cand.family] = {
            "label": cand.label,
            "registry_id": cand.registry_id,
            "verdict": verdict,
            "reasons": reasons,
            "passing_ic_slots": ic_pass_n,
            "n_ok": len(ok_slots),
            "n_total": len(slots),
            "median_haircut_sharpe": med_hsr,
            "median_dsr": med_dsr,
        }

    payload = {
        "generated": datetime.now(UTC).isoformat(),
        "framework": "Edge Research Factory Sprint 2 — real funding factors (BL-718)",
        "data": {
            "funding_dir": str(funding_dir),
            "coverage": {
                a: {
                    "settlements": len(pd.read_parquet(funding_dir / f"{a}.parquet"))
                    if (funding_dir / f"{a}.parquet").exists()
                    else 0
                }
                for a, _ in [(s[0], s[1]) for c in CANDIDATES for s in c.slots]
            },
        },
        "thresholds": {
            "icir_threshold": ICIR_THRESHOLD,
            "ic_block_t_threshold": IC_BLOCK_T_THRESHOLD,
            "haircut_pct": IC_HAIRCUT_PCT,
            "haircut_sharpe_min": HAIRCUT_SHARPE_GATE,
            "dsr_min": DSR_MIN,
            "psr_min": PSR_MIN,
            "kill_min_passing_slots": KILL_MIN_PASSING_SLOTS,
        },
        "slots": [asdict(s) for s in all_slots],
        "verdicts": verdicts,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sprint-2.json").write_text(json.dumps(payload, indent=2, default=str))
    _write_md_report(payload, out_dir / "sprint-2.md")
    print(f"\nReport → {out_dir / 'sprint-2.md'}")
    return 0


def _write_md_report(payload: dict[str, Any], path: Path) -> None:
    verdicts: dict[str, dict[str, Any]] = payload["verdicts"]
    slots: list[dict[str, Any]] = payload["slots"]
    lines = [
        "# BL-718 — Edge Factory Sprint 2 (real funding factors) Qualification Report",
        "",
        f"**Generated**: {payload['generated']}",
        "**Framework**: Edge Research Factory · ADR-017 (DSR/PSR) · BL-706 (IC screen) · BL-707 (Haircut Sharpe).",  # noqa: E501
        "",
        "## Top-line verdict",
        "",
    ]
    for fam, v in verdicts.items():
        lines.append(
            f"- **{v['label']}** (`{fam}`) → **{v['verdict']}** "
            f"(slots: {v['passing_ic_slots']} IC-pass / {v['n_ok']} OK / {v['n_total']} total; "
            f"median haircut Sharpe {v['median_haircut_sharpe']:.4f}, "
            f"median DSR {v['median_dsr']:.4f})"
        )
    lines += ["", "## Per-slot tables", ""]
    for fam in verdicts:
        lines += [f"### {fam}", ""]
        rows = [s for s in slots if s["family"] == fam and s["status"] == "OK"]
        if not rows:
            lines += ["_No OK slots._", ""]
            continue
        lines += [
            "| asset | tf | n_bars | n_pairs | IC | ICIR haircut | t-block | obs SR | haircut SR | DSR | status |",  # noqa: E501
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for s in rows:
            lines.append(
                f"| {s['asset']} | {s['timeframe']} | {s['n_bars']} | {s['n_pairs']} | "
                f"{'✅' if s['ic_passed'] else '❌'} {s['ic_mean']:+.4f} | "
                f"{s['icir_haircut']:+.4f} | "
                f"{s['ic_t_block']:+.2f} | {s['observed_sharpe']:+.3f} | "
                f"{s['haircut_sharpe']:+.3f} | "
                f"{(s['dsr'] or 0):.4f} | {s['status']} |"
            )
        lines.append("")
    insuf = [s for s in slots if s["status"] != "OK"]
    if insuf:
        lines += ["## Insufficient-data slots", ""]
        for s in insuf:
            lines.append(f"- {s['family']}/{s['asset']} {s['timeframe']}: {s['n_pairs']} pairs")
    lines += [
        "",
        "## Thresholds (frozen)",
        "",
        f"- `icir_haircut_min`: {ICIR_THRESHOLD}",
        f"- `ic_block_t_min`: {IC_BLOCK_T_THRESHOLD}",
        f"- `haircut_pct`: {IC_HAIRCUT_PCT}",
        f"- `haircut_sharpe_min`: {HAIRCUT_SHARPE_GATE}",
        f"- `dsr_min`: {DSR_MIN}",
        f"- `kill_min_passing_slots`: {KILL_MIN_PASSING_SLOTS}",
        "",
    ]
    path.write_text("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
