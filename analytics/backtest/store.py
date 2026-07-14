"""Persistence layer for :class:`BacktestResult`.

The backtest engines already compute a fully-populated ``BacktestResult``
(equity curve, trade log, profit factor, CAGR, total return, ...), but
until now nothing persisted it — so the dashboard API could only serve
placeholder zeros read from GA checkpoints.

``BacktestResultStore`` writes each run as JSON (a per-run file plus a
``latest.json`` pointer) so the API can read the most recent real
result.  ``to_performance_summary`` and ``to_equity_points`` bridge a
``BacktestResult`` into the shapes the dashboard expects.
"""

from __future__ import annotations

import json
from pathlib import Path

from analytics.backtest.result import BacktestResult

#: Default store location: ``<project_root>/results/``.
_DEFAULT_DIR = Path(__file__).resolve().parents[2] / "results"


class BacktestResultStore:
    """JSON file store for backtest results."""

    def __init__(self, directory: Path | str | None = None) -> None:
        self.dir: Path = Path(directory) if directory else _DEFAULT_DIR

    def save(self, result: BacktestResult) -> Path:
        """Persist *result* as ``{run_id}.json`` and refresh ``latest.json``.

        Returns the path of the ``latest.json`` pointer.
        """
        self.dir.mkdir(parents=True, exist_ok=True)
        payload = result.to_dict()
        run_id = result.run_id or "latest"

        (self.dir / f"{run_id}.json").write_text(json.dumps(payload, default=str))
        latest_path = self.dir / "latest.json"
        latest_path.write_text(json.dumps(payload, default=str))
        return latest_path

    def load_latest(self) -> BacktestResult | None:
        """Load the most recently saved result, or ``None`` if absent."""
        return self._load(self.dir / "latest.json")

    def load(self, run_id: str) -> BacktestResult | None:
        """Load a specific run by id, or ``None`` if absent."""
        return self._load(self.dir / f"{run_id}.json")

    def _load(self, path: Path) -> BacktestResult | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return BacktestResult.model_validate(data)
        except (json.JSONDecodeError, ValueError, OSError):
            return None


def to_performance_summary(result: BacktestResult) -> dict[str, object]:
    """Build a dashboard performance summary from a real ``BacktestResult``.

    Unlike the checkpoint-based summary, every field here reflects an
    actual backtest — no placeholder zeros.
    """
    return {
        "sharpe": result.sharpe_ratio,
        "sortino": result.sortino_ratio,
        "calmar": result.calmar_ratio,
        "max_drawdown": result.max_drawdown,
        "profit_factor": result.profit_factor,
        "cagr": result.cagr,
        "total_return": result.total_return,
        "win_rate": result.win_rate,
        "total_trades": result.total_trades,
        "volatility": result.volatility,
        "run_id": result.run_id,
        "instrument": result.instrument,
        "strategy_name": result.strategy_name,
        "engine": result.engine,
        "start_time": result.start_time.isoformat() if result.start_time else None,
        "end_time": result.end_time.isoformat() if result.end_time else None,
    }


def to_equity_points(result: BacktestResult) -> list[dict[str, float]]:
    """Convert a result's equity curve into ``{index, equity}`` points."""
    return [{"index": float(i), "equity": float(v)} for i, v in enumerate(result.equity_curve)]
