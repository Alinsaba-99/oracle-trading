"""Smoke test: import purgedcv + deflated_sharpe to verify install.

Run: .venv/bin/python scripts/smoke_dsr_packages.py
"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from purgedcv import (
            CombinatorialPurgedCV,
            PurgedKFold,
            deflated_sharpe_ratio,
            probabilistic_sharpe_ratio,
            probability_of_backtest_overfitting,
        )
    except ImportError as e:
        print(f"FAIL purgedcv import: {e}")
        return 1

    try:
        from deflated_sharpe import deflated_sharpe_ratio as dsr_standalone
    except ImportError as e:
        print(f"WARN deflated_sharpe standalone import failed (non-blocking): {e}")

    try:
        import numpy as np

        rng = np.random.default_rng(42)
        returns = rng.normal(0.0005, 0.01, size=252)
        var_sharpe = float(returns.var())
        n_trials = 50
        dsr_value = deflated_sharpe_ratio(returns=returns, n_trials=n_trials, var_sharpe=var_sharpe)
        sharpe = float(returns.mean() / returns.std() * (252**0.5))
        print(f"OK DSR sanity: sharpe={sharpe:.3f}, n_trials={n_trials}, DSR={dsr_value}")
    except Exception as e:
        print(f"FAIL DSR sanity run: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
