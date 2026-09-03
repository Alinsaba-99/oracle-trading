#!/usr/bin/env python3
"""BL-718 Sprint 2b — Extended cross-section + perp-basis carry (EF-007).

Two extensions of the Sprint 2 qualification:

1. **Cross-section robustness** — rerun EF-001 / EF-006 funding factors
   on the 5 extra symbols backfilled in ``data/lake/raw/funding``
   (XRP, BNB, DOGE, ADA, LINK).  A factory edge that only lives on ETH
   is not an edge; the cross-section verdict is honest only when the
   new slots are scored with the SAME frozen gauntlet.
2. **perp-basis-carry** (EF-007) — factor = − annualised basis
   z-score, where basis = (perp_close / spot_close − 1) annualised over
   the funding horizon, from ``data/lake/raw/perp/{SYM}_1h.parquet``
   vs the lake spot 1h close.  Amplification report (2026-09-03)
   mandates an IS/OOS split at 2024-03 (ETF quarter): the factor is
   evaluated on the full sample AND separately pre/post split — a GO
   requires the post-split half to pass the IC screen on its own.

Gauntlet: identical to Sprint 2 (frozen thresholds, no overrides).

Outputs:
    docs/reports/edge-factory/sprint-2b.md
    docs/reports/edge-factory/sprint-2b.json

Usage:
    uv run --frozen python scripts/run_factory_sprint2b_extended.py
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

from scripts.run_factory_sprint2_qualification import (  # noqa: E402
    DEFAULT_HORIZON_HOURLY,
    DSR_MIN,
    HAIRCUT_SHARPE_GATE,
    IC_BLOCK_T_THRESHOLD,
    IC_HAIRCUT_PCT,
    ICIR_THRESHOLD,
    KILL_MIN_PASSING_SLOTS,
    VERDICT_GO,
    VERDICT_NO_GO,
    SlotResult,
    evaluate_slot,
    extremum_reversal_factor,
    funding_z_factor,
    load_funding_onto_prices,
)

# Extra funding slots for the cross-section check (Sprint 2 symbols
# BTC/ETH/SOL are already scored in sprint-2.md — not duplicated here).
XS_SYMBOLS = ("XRPUSDT", "BNBUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT")

# IS/OOS split for EF-007 (post-ETF quarter, per amplification report).
ETF_SPLIT = pd.Timestamp("2024-03-01", tz="UTC")


def perp_spot_basis(perp_dir: Path, lake_root: Path, asset: str) -> pd.Series | None:
    """Signed annualised basis: perp vs spot close on the 1h grid.

    Returns None when either file is missing or overlap < 500 bars.
    Basis is computed per bar (no lookahead: both closes are the bar
    close; the factor built on it is shifted by the gauntlet horizon).
    """
    ppath = perp_dir / f"{asset}_1h.parquet"
    spath = lake_root / f"{asset}_1h.parquet"
    if not ppath.exists() or not spath.exists():
        return None
    perp = pd.read_parquet(ppath, columns=["open_time_ms", "close"])
    perp.index = pd.to_datetime(perp["open_time_ms"].astype("int64") * 1_000_000, utc=True)
    perp = perp["close"].astype(float).sort_index()
    perp = perp[~perp.index.duplicated(keep="last")]
    spot = pd.read_parquet(spath, columns=["timestamp", "close"])
    spot.index = pd.to_datetime(spot["timestamp"], utc=True)
    spot = spot["close"].astype(float).sort_index()
    spot = spot[~spot.index.duplicated(keep="last")]
    df = pd.concat([spot.rename("spot"), perp.rename("perp")], axis=1).dropna()
    if len(df) < 500:
        return None
    basis = (df["perp"] / df["spot"] - 1.0).rename("basis")
    return basis


def basis_carry_factor(
    basis: pd.Series, spot: pd.Series, horizon: int
) -> tuple[pd.Series, pd.Series]:
    """EF-007: fade extreme basis — factor = − zscore(basis, 30d).

    Extreme positive basis (perp premium, crowded longs paying carry)
    → factor negative → expected negative spot forward return; extreme
    discount → long.  Same contrarian IC direction as the registry.
    """
    z = (basis - basis.rolling(720, min_periods=360).mean()) / basis.rolling(
        720, min_periods=360
    ).std(ddof=1).replace(0.0, np.nan)
    factor = (-z).rename("ef007")
    fwd = (spot.shift(-horizon) / spot - 1.0).rename("fwd_ret")
    return factor, fwd


FactorFn3 = Callable[[pd.Series, pd.Series, int], tuple[pd.Series, pd.Series]]


@dataclass(frozen=True)
class Task:
    family: str
    label: str
    registry_id: str
    factor_fn: FactorFn3
    slots: tuple[tuple[str, str], ...]
    needs: str  # "funding" | "basis"


def _funding_tasks() -> list[Task]:
    return [
        Task(
            family="funding_extremum_reversal_xs",
            label="EF-001 Reversal (cross-section)",
            registry_id="crypto-microstructure/EF-001",
            factor_fn=extremum_reversal_factor,
            slots=tuple((s, "1h") for s in XS_SYMBOLS),
            needs="funding",
        ),
        Task(
            family="funding_z_feature_xs",
            label="EF-006 Funding Z (cross-section)",
            registry_id="crypto-microstructure/EF-006",
            factor_fn=funding_z_factor,
            slots=tuple((s, "1h") for s in XS_SYMBOLS),
            needs="funding",
        ),
    ]


def _basis_tasks() -> list[Task]:
    return [
        Task(
            family="perp_basis_carry",
            label="EF-007 Perp-Basis Carry",
            registry_id="crypto-microstructure/EF-007",
            factor_fn=basis_carry_factor,
            slots=(("BTCUSDT", "1h"), ("ETHUSDT", "1h")),
            needs="basis",
        )
    ]


def _score(tasks: list[Task], args: argparse.Namespace) -> tuple[list[SlotResult], dict[str, Any]]:
    funding_dir = Path(args.funding_dir)
    lake_root = Path(args.lake_root)
    perp_dir = Path(args.perp_dir)
    all_slots: list[SlotResult] = []
    verdicts: dict[str, Any] = {}
    for task in tasks:
        slots: list[SlotResult] = []
        for asset, tf in task.slots:
            if task.needs == "funding":
                loaded = load_funding_onto_prices(funding_dir, lake_root, asset)
                series_pair = loaded
                close = loaded[0] if loaded else None
            else:
                basis = perp_spot_basis(perp_dir, lake_root, asset)
                series_pair = None if basis is None else (basis, None)
                close = None
                if basis is not None:
                    spot = pd.read_parquet(
                        lake_root / f"{asset}_1h.parquet", columns=["timestamp", "close"]
                    )
                    spot.index = pd.to_datetime(spot["timestamp"], utc=True)
                    close = spot["close"].astype(float).sort_index()
                    close = close[~close.index.duplicated(keep="last")]
                    series_pair = (basis, None)
            if series_pair is None or close is None:
                print(f"SKIP {asset} {tf}: data missing", file=sys.stderr)
                continue
            if task.needs == "funding":
                close_s, funding_s = loaded  # type: ignore[misc]
                factor, fwd = task.factor_fn(close_s, funding_s, DEFAULT_HORIZON_HOURLY)
                res = evaluate_slot(
                    task.family,
                    task.label,
                    asset,
                    factor,
                    fwd,
                    close_s,
                    n_bars=int(close_s.size),
                    horizon=DEFAULT_HORIZON_HOURLY,
                    boot_n=args.boot_n,
                )
                slots.append(res)
                all_slots.append(res)
            else:
                factor, fwd = task.factor_fn(series_pair[0], close, DEFAULT_HORIZON_HOURLY)
                full = evaluate_slot(
                    task.family,
                    task.label,
                    asset,
                    factor,
                    fwd,
                    close,
                    n_bars=int(close.size),
                    horizon=DEFAULT_HORIZON_HOURLY,
                    boot_n=args.boot_n,
                )
                slots.append(full)
                all_slots.append(full)
                # EF-007 amplification mandate: IS/OOS split at ETF quarter
                pre = factor[factor.index < ETF_SPLIT]
                pre_close = close[close.index < ETF_SPLIT]
                pre_fwd = fwd[fwd.index < ETF_SPLIT]
                post = factor[factor.index >= ETF_SPLIT]
                post_close = close[close.index >= ETF_SPLIT]
                post_fwd = fwd[fwd.index >= ETF_SPLIT]
                for tag, f, c, fw in (
                    ("pre_2024-03", pre, pre_close, pre_fwd),
                    ("post_2024-03", post, post_close, post_fwd),
                ):
                    res = evaluate_slot(
                        task.family,
                        f"{task.label} [{tag}]",
                        asset,
                        f,
                        fw,
                        c,
                        n_bars=int(c.size),
                        horizon=DEFAULT_HORIZON_HOURLY,
                        boot_n=args.boot_n,
                    )
                    slots.append(res)
                    all_slots.append(res)
            best = max(
                (s for s in slots if s.asset == asset and s.status == "OK"),
                key=lambda s: s.icir_haircut,
                default=None,
            )
            if best is not None:
                print(
                    f"{task.family:32s} {asset:8s} IC={best.ic_mean:+.4f} "
                    f"ICIRh={best.icir_haircut:+.4f} t={best.ic_t_block:+.2f} "
                    f"pass={best.ic_passed}"
                )
        ok_slots = [s for s in slots if s.status == "OK"]
        ic_pass_n = sum(1 for s in ok_slots if s.ic_passed)
        med_hsr = float(np.median([s.haircut_sharpe for s in ok_slots])) if ok_slots else 0.0
        dsr_vals = [s.dsr for s in ok_slots if s.dsr is not None]
        med_dsr = float(np.median(dsr_vals)) if dsr_vals else 0.0
        reasons = []
        if ic_pass_n < KILL_MIN_PASSING_SLOTS:
            reasons.append(f"only {ic_pass_n} slots pass the IC screen")
        if not ok_slots or med_hsr <= HAIRCUT_SHARPE_GATE:
            reasons.append(f"median haircut Sharpe {med_hsr:.4f} not > 0.0")
        if not ok_slots or med_dsr < DSR_MIN:
            reasons.append(f"median DSR {med_dsr:.4f} < 0.5")
        verdict = VERDICT_GO if not reasons else VERDICT_NO_GO
        verdicts[task.family] = {
            "label": task.label,
            "registry_id": task.registry_id,
            "verdict": verdict,
            "reasons": reasons,
            "passing_ic_slots": ic_pass_n,
            "n_ok": len(ok_slots),
            "n_total": len(slots),
            "median_haircut_sharpe": med_hsr,
            "median_dsr": med_dsr,
        }
    return all_slots, verdicts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--funding-dir", default="data/lake/raw/funding")
    parser.add_argument("--perp-dir", default="data/lake/raw/perp")
    parser.add_argument("--lake-root", default="data/lake/curated")
    parser.add_argument("--out-dir", default="docs/reports/edge-factory")
    parser.add_argument("--boot-n", type=int, default=500)
    args = parser.parse_args()
    out_dir = Path(args.out_dir)

    tasks = _funding_tasks()
    perp_path = Path(args.perp_dir) / "BTCUSDT_1h.parquet"
    if perp_path.exists():
        tasks += _basis_tasks()
    all_slots, verdicts = _score(tasks, args)

    payload: dict[str, Any] = {
        "generated": datetime.now(UTC).isoformat(),
        "framework": "Edge Research Factory Sprint 2b — cross-section + basis (BL-718)",
        "slots": [asdict(s) for s in all_slots],
        "verdicts": verdicts,
        "thresholds": {
            "icir_threshold": ICIR_THRESHOLD,
            "ic_block_t_threshold": IC_BLOCK_T_THRESHOLD,
            "haircut_pct": IC_HAIRCUT_PCT,
            "haircut_sharpe_min": HAIRCUT_SHARPE_GATE,
            "dsr_min": DSR_MIN,
            "kill_min_passing_slots": KILL_MIN_PASSING_SLOTS,
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sprint-2b.json").write_text(json.dumps(payload, indent=2, default=str))
    lines = [
        "# Sprint 2b — Cross-section extension + EF-007 basis",
        "",
        f"**Generated**: {payload['generated']}",
        "",
        "## Verdicts",
        "",
    ]
    for fam, v in verdicts.items():
        lines.append(
            f"- **{v['label']}** (`{fam}`) → **{v['verdict']}** "
            f"({v['passing_ic_slots']} IC-pass / {v['n_ok']} OK / {v['n_total']} total; "
            f"median hSR {v['median_haircut_sharpe']:.3f}, median DSR {v['median_dsr']:.3f})"
        )
    lines += [
        "",
        "## Slots",
        "",
        "| family | asset | IC | ICIRh | t | pass | hSR | DSR |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in payload["slots"]:
        if s["status"] != "OK":
            continue
        lines.append(
            f"| {s['family']} | {s['label']} @ {s['asset']} | {s['ic_mean']:+.4f} | "
            f"{s['icir_haircut']:+.4f} | {s['ic_t_block']:+.2f} | "
            f"{'✅' if s['ic_passed'] else '❌'} | {s['haircut_sharpe']:+.2f} | "
            f"{(s['dsr'] or 0):.3f} |"
        )
    (out_dir / "sprint-2b.md").write_text("\n".join(lines) + "\n")
    print(f"\nReport → {out_dir / 'sprint-2b.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
