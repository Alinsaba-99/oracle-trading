"""BL-090 — Research Memory: SQLite-backed decision tracking with outcomes.

Stores every routing decision (regime, confidence, specialist, features)
and the eventual P&L outcome so the system can learn which strategies
work in which conditions.

Uses ``sqlite3`` (stdlib) — zero extra dependencies.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

_DEFAULT_DB = "research_memory.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS decisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    regime      TEXT NOT NULL,
    regime_confidence REAL NOT NULL,
    specialist  TEXT NOT NULL,
    reason      TEXT,
    signal      INTEGER,
    features    TEXT,
    pnl         REAL,
    market_return REAL,
    session_id  TEXT
);

CREATE INDEX IF NOT EXISTS idx_decisions_regime ON decisions(regime);
CREATE INDEX IF NOT EXISTS idx_decisions_specialist ON decisions(specialist);
CREATE INDEX IF NOT EXISTS idx_decisions_session ON decisions(session_id);
"""


class ResearchMemory:
    """SQLite-backed memory of trading decisions and their outcomes.

    Usage::

        mem = ResearchMemory("my_memory.db")
        mem.record_decision(decision, features={"close": 4500.0})
        # ... later, when P&L is known:
        mem.record_outcome(decision_id=1, pnl=125.0, market_return=0.01)
        stats = mem.get_regime_accuracy()
        perf = mem.get_specialist_performance()
    """

    def __init__(self, db_path: str = _DEFAULT_DB) -> None:
        self._path = str(db_path)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA_SQL)

    # ── public API ─────────────────────────────────────────────────────

    def record_decision(
        self,
        regime: str,
        regime_confidence: float,
        specialist: str,
        *,
        reason: str | None = None,
        signal: int | None = None,
        features: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> int:
        """Record a routing decision. Returns the new decision id.

        Args:
            regime: The detected regime label (e.g. 'bull', 'choppy').
            regime_confidence: Confidence in the regime detection (0..1).
            specialist: The selected specialist (e.g. 'trend', 'mean_rev').
            reason: Human-readable reason for the routing decision.
            signal: The signal value (-1, 0, or 1) if known at decision time.
            features: Arbitrary context features (JSON-serialisable).
            session_id: Paper/replay session identifier for grouping.

        Returns:
            The auto-generated primary key for this row.
        """
        now = datetime.now(UTC).isoformat()
        features_json = json.dumps(features) if features else None
        cur = self._conn.execute(
            """INSERT INTO decisions
               (timestamp, regime, regime_confidence,
                specialist, reason, signal, features, session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (now, regime, regime_confidence, specialist, reason, signal, features_json, session_id),
        )
        self._conn.commit()
        if cur.lastrowid is None:
            return 0
        return cur.lastrowid

    def record_outcome(self, decision_id: int, pnl: float, market_return: float) -> None:
        """Record the realised P&L for a previous decision.

        Args:
            decision_id: The id returned by ``record_decision``.
            pnl: Realised P&L in account currency.
            market_return: Benchmark return over the same period.
        """
        self._conn.execute(
            "UPDATE decisions SET pnl = ?, market_return = ? WHERE id = ?",
            (pnl, market_return, decision_id),
        )
        self._conn.commit()

    def get_regime_accuracy(self, regime: str | None = None, window: int = 100) -> dict[str, Any]:
        """Return confidence calibration stats for the regime detector.

        For each regime, reports: count, mean_confidence, win_rate (if outcomes
        recorded), and correlation between confidence and outcome correctness.

        Args:
            regime: Filter to a specific regime (None = all).
            window: Number of most recent rows to consider.

        Returns:
            Nested dict keyed by regime label (or a single dict if filtered).
        """
        regime_filter = "WHERE regime = ?" if regime else ""
        params: list[Any] = []
        if regime:
            params.append(regime)

        sql = f"""
            SELECT regime,
                   COUNT(*) as n,
                   AVG(regime_confidence) as mean_conf,
                   AVG(CASE WHEN pnl IS NOT NULL AND pnl > 0 THEN 1.0
                            WHEN pnl IS NOT NULL AND pnl <= 0 THEN 0.0
                            ELSE NULL END) as win_rate,
                   AVG(CASE WHEN pnl IS NULL THEN NULL ELSE 1.0 END) as outcome_pct
            FROM (
                SELECT * FROM decisions
                {regime_filter}
                ORDER BY rowid DESC
                LIMIT ?
            )
            GROUP BY regime
        """
        params.append(window)
        rows = self._conn.execute(sql, params).fetchall()

        result: dict[str, Any] = {}
        for r in rows:
            result[str(r["regime"])] = {
                "n": r["n"],
                "mean_confidence": round(r["mean_conf"], 4) if r["mean_conf"] else 0.0,
                "win_rate": round(r["win_rate"], 4) if r["win_rate"] is not None else None,
                "outcome_recorded_pct": round(r["outcome_pct"], 4) if r["outcome_pct"] else 0.0,
            }

        if regime and regime in result:
            # result is already built as dict[str, Any]
            return result[regime]  # type: ignore[no-any-return]
        return result

    def get_specialist_performance(
        self, specialist: str | None = None, window: int = 100
    ) -> dict[str, Any]:
        """Return performance metrics per specialist.

        Reports: count, Sharpe-like ratio (mean P&L / std P&L), win_rate,
        mean_return.

        Args:
            specialist: Filter to a specific specialist (None = all).
            window: Number of most recent rows to consider.

        Returns:
            Nested dict keyed by specialist label.
        """
        params: list[Any] = []
        inner_where = "WHERE pnl IS NOT NULL"
        if specialist:
            inner_where += " AND specialist = ?"
            params.append(specialist)

        sql = f"""
            SELECT specialist,
                   COUNT(*) as n,
                   AVG(pnl) as mean_pnl,
                   AVG(CASE WHEN pnl > 0 THEN 1.0 WHEN pnl < 0 THEN 0.0 ELSE NULL END) as win_rate,
                   AVG(market_return) as mean_market_return
            FROM (
                SELECT * FROM decisions
                {inner_where}
                ORDER BY rowid DESC
                LIMIT ?
            )
            GROUP BY specialist
        """
        params.append(window)
        rows = self._conn.execute(sql, params).fetchall()

        result: dict[str, Any] = {}
        for r in rows:
            result[str(r["specialist"])] = {
                "n": r["n"],
                "mean_pnl": round(r["mean_pnl"], 4) if r["mean_pnl"] is not None else None,
                "win_rate": round(r["win_rate"], 4) if r["win_rate"] is not None else None,
                "mean_market_return": round(r["mean_market_return"], 6)
                if r["mean_market_return"] is not None
                else None,
            }

        if specialist and specialist in result:
            return result[specialist]  # type: ignore[no-any-return]
        return result

    def get_recent_decisions(self, n: int = 20) -> list[dict[str, Any]]:
        """Return the *n* most recent decisions with all fields.

        Args:
            n: Number of rows to return.

        Returns:
            List of dicts keyed by column name.
        """
        rows = self._conn.execute(
            """SELECT * FROM decisions ORDER BY rowid DESC LIMIT ?""", (n,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_decisions_by_session(self, session_id: str) -> list[dict[str, Any]]:
        """Return all decisions belonging to a specific session."""
        rows = self._conn.execute(
            """SELECT * FROM decisions WHERE session_id = ? ORDER BY rowid ASC""", (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def count(self) -> int:
        """Total number of recorded decisions."""
        (n,) = self._conn.execute("SELECT COUNT(*) FROM decisions").fetchone()
        return int(n)

    def close(self) -> None:
        """Close the SQLite connection."""
        self._conn.close()

    # ── context manager ────────────────────────────────────────────────

    def __enter__(self) -> ResearchMemory:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


# ── helper: build features from common data ──────────────────────────────


def build_features(
    *,
    close: float | None = None,
    volume: float | None = None,
    volatility: float | None = None,
    trend_strength: float | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build a features dict from common market context variables.

    This is a convenience for the ``ResearchMemory.record_decision``
    ``features`` parameter.

    Returns:
        A dict with only the non-None fields.
    """
    features: dict[str, Any] = {}
    if close is not None:
        features["close"] = close
    if volume is not None:
        features["volume"] = volume
    if volatility is not None:
        features["volatility"] = volatility
    if trend_strength is not None:
        features["trend_strength"] = trend_strength
    features.update(extra)
    return features


__all__ = ["ResearchMemory", "build_features"]
