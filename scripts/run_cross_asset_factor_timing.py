"""BL-202 — Cross-asset factor timing.

Port FactorTimingEngine (G6-I-01) su strumenti diversi da ES:
BTC/USDT 1h, ES 1h, GC, EURUSD via DataRegistry.

Output: `logs/cross_asset_factor_timing.json` con ranking per strumento.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from analytics.regime.detector import RegimeDetector
from analytics.strategy.factor_timing.rank import FactorTimingEngine
from analytics.strategy.lorentzian import LorentzianKNN
from analytics.strategy.signals import DonchianBreakout, EmaTrend, RsiReversion


def _human_factors() -> dict[str, callable]:
    return {
        "ema_10_30_close_minus_open": lambda df: (df["close"] - df["open"]).rolling(10).mean(),
        "rsi_14_close": lambda df: df["close"],
        "donchian_high_minus_low_20": lambda df: (
            df["high"].rolling(20).max() - df["low"].rolling(20).min()
        ),
        "close_pct_change_5": lambda df: df["close"].pct_change(5),
        "volume_mean_20": lambda df: df["volume"].rolling(20).mean(),
        "high_low_spread": lambda df: df["high"] - df["low"],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data", nargs="+", default=["data/ohlcv/BTC_USDT_1h.parquet"])
    p.add_argument("--horizon", type=int, default=5)
    p.add_argument("--output", default="logs/cross_asset_factor_timing.json")
    args = p.parse_args()

    catalog = {
        "lorentzian_signal": lambda df: LorentzianKNN(
            k=4, lookahead=args.horizon, max_bars_back=80, feature_count=3
        ).compute(df),
        "ema_trend_10_30": lambda df: EmaTrend(fast=10, slow=30).compute(df),
        "rsi_reversion_14": lambda df: RsiReversion(period=14).compute(df),
        "donchian_breakout_20": lambda df: DonchianBreakout(period=20).compute(df),
    }

    detector = RegimeDetector()
    instrument_results = {}

    for path_str in args.data:
        path = Path(path_str)
        if not path.exists():
            print(f"WARN: {path} missing, skip")
            continue
        df = pl.read_parquet(path).rename({c: c.lower() for c in pl.read_parquet(path).columns})
        if len(df) < 100:
            print(f"WARN: {path} too short ({len(df)} bars), skip")
            continue

        returns = df["close"].pct_change().fill_null(0.0).to_numpy()
        try:
            detector.fit(returns)
            regime_label, regime_conf, _ = detector.detect(returns)
        except Exception:
            regime_label, regime_conf = "unknown", 0.0

        engine = FactorTimingEngine(catalog=catalog)
        try:
            rank = engine.rank(df, "close", horizon=args.horizon)
        except Exception as exc:
            print(f"WARN: rank failed for {path}: {exc}")
            continue

        instrument_results[path.stem] = {
            "data": str(path),
            "n_bars": len(df),
            "regime": str(regime_label),
            "regime_confidence": round(float(regime_conf), 4),
            "factor_ranking": [
                {
                    "factor": r.name,
                    "rank_ic": round(r.effectiveness.rank_ic, 4),
                    "icir": round(r.effectiveness.icir, 4),
                    "recent_rank_ic": round(r.effectiveness.rank_ic_recent, 4),
                    "decay_state": r.effectiveness.decay_state,
                    "passes_null": r.passes_null_benchmark,
                }
                for r in rank
            ],
            "top_factor": rank[0].name if rank else None,
        }
        top_factor = instrument_results[path.stem]["top_factor"]
        print(f"\n{path.stem}: regime={regime_label} top={top_factor}")
        for r in rank[:3]:
            eff = r.effectiveness
            print(f"  {r.name:<40} IC={eff.rank_ic:+.3f} dec={eff.decay_state}")

    out = {
        "metadata": {
            "horizon": args.horizon,
            "data_paths": args.data,
            "timestamp": "2026-07-25",
            "bl": "BL-202",
        },
        "instruments": instrument_results,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nSaved to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
