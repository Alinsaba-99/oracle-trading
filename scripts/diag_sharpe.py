"""Diagnose the risk metrics computation against a real backtest."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from analytics.backtest.config import BacktestConfig
from analytics.backtest.engines.vectorized import (
    VectorizedEngine,
    _periods_per_year,
    _risk_metrics_from_equity,
)
from analytics.backtest.providers import DataRegistry
from analytics.strategy.spec import StrategySpec

_ROOT = Path(__file__).parent.parent


def main() -> int:
    registry = DataRegistry(root=_ROOT / "data" / "ohlcv")
    entry = sys.argv[1] if len(sys.argv) > 1 else "donchian_breakout"
    instrument = sys.argv[2] if len(sys.argv) > 2 else "GOLD"
    tf = sys.argv[3] if len(sys.argv) > 3 else "1d"
    spec = StrategySpec(name="diag", instrument=instrument, entry=entry, timeframe=tf)
    df = registry.get_ohlcv(spec.lake_instrument_id(), spec.timeframe)
    print(f"spec: {entry} {instrument} {tf}")
    print(f"data: {df.height} rows, {df['timestamp'].min()} .. {df['timestamp'].max()}")

    engine = VectorizedEngine()
    result = engine.run(df, spec.build_signal(), BacktestConfig())
    equity = np.asarray(engine.equity_curve(), dtype=np.float64)
    print(f"result.sharpe_ratio = {result.sharpe_ratio:.4f}")

    print(f"\nequity curve: len={equity.size}")
    print(f"  finite:      {int(np.isfinite(equity).sum())}")
    print(f"  positive:    {int((equity > 0).sum())}")
    print(f"  nan:         {int(np.isnan(equity).sum())}")
    print(f"  first/last:  {equity[0]:.2f} / {equity[-1]:.2f}")
    print(f"  min/max:     {np.nanmin(equity):.2f} / {np.nanmax(equity):.2f}")

    valid = equity[np.isfinite(equity) & (equity > 0)]
    print(f"\nafter filter: {valid.size} (dropped {equity.size - valid.size})")

    returns = np.diff(np.log(valid))
    returns = returns[np.isfinite(returns)]
    print(f"log returns:  n={returns.size}")
    print(f"  mean:       {np.mean(returns):.8f}")
    print(f"  std:        {np.std(returns, ddof=1):.8f}")
    print(f"  ratio:      {np.mean(returns) / np.std(returns, ddof=1):.6f}")
    nonzero = returns[returns != 0.0]
    print(f"  non-zero:   {nonzero.size} ({100.0 * nonzero.size / max(returns.size, 1):.1f}%)")
    print(f"  max abs:    {np.max(np.abs(returns)):.6f}")

    ppy = _periods_per_year(df["timestamp"].to_pandas())
    print(f"\nperiods_per_year: {ppy:.2f}  (sqrt={np.sqrt(ppy):.3f})")

    sharpe, sortino, calmar, vol = _risk_metrics_from_equity(
        equity, result.max_drawdown * 100.0, periods_per_year=ppy
    )
    print(f"  sharpe={sharpe:.4f} sortino={sortino:.4f} calmar={calmar:.4f} vol={vol:.2f}%")

    years = (df["timestamp"].max() - df["timestamp"].min()).days / 365.25
    cagr = (equity[-1] / equity[0]) ** (1.0 / years) - 1.0
    print(
        f"\nreality check: {years:.1f}y, CAGR={cagr * 100:.2f}%, "
        f"DD={result.max_drawdown * 100:.1f}%"
    )
    print(f"  a {cagr * 100:.1f}% CAGR strategy should have Sharpe well under 2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
