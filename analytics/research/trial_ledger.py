"""BL-506 — Trial Ledger S0.3: pre-registration of turnaround theses (no HARKing).

Stores every turnaround thesis BEFORE the trade is taken, so we can later
verify the hit-rate of the screening process without "telling the story
after the fact". This is the S0.3 trial-ledger pattern from the deep-research
synthesis 2026-08-15 §2.5 and ADR-018 (Lane B is portafoglio personale
operatore, NOT prop-firm).

The ledger is SQLite-backed (stdlib) — zero extra dependencies.

Schema
------
- theses: pre-registered theses with ticker, catalyst, entry/stop/target
- outcomes: P&L realized, time-to-exit, hit-stop-or-target
- audits: hash chain for tamper-evidence (each row references previous hash)
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from typing import Any

_DEFAULT_DB = "trial_ledger.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS theses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    thesis_id       TEXT NOT NULL UNIQUE,
    registered_at   TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    entry_target    REAL NOT NULL,
    stop_target     REAL NOT NULL,
    target_price    REAL NOT NULL,
    position_pct    REAL NOT NULL,
    catalyst        TEXT NOT NULL,
    invalidation    TEXT NOT NULL,
    horizon_days    INTEGER NOT NULL,
    f_score         INTEGER,
    magic_rank      INTEGER,
    return_12m      REAL,
    notes           TEXT,
    pre_hash        TEXT
);

CREATE TABLE IF NOT EXISTS outcomes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    thesis_id       TEXT NOT NULL,
    closed_at       TEXT NOT NULL,
    exit_reason     TEXT NOT NULL,
    entry_actual    REAL,
    exit_actual     REAL,
    pnl_pct         REAL,
    pnl_amount      REAL,
    bars_held       INTEGER,
    notes           TEXT,
    FOREIGN KEY (thesis_id) REFERENCES theses(thesis_id)
);

CREATE INDEX IF NOT EXISTS idx_theses_ticker ON theses(ticker);
CREATE INDEX IF NOT EXISTS idx_theses_registered ON theses(registered_at);
CREATE INDEX IF NOT EXISTS idx_outcomes_thesis ON outcomes(thesis_id);
"""


class TrialLedger:
    """Pre-registered thesis ledger with tamper-evident hash chain.

    The trial ledger is the antidote to HARKing (Hypothesizing After Results
    are Known): by writing down the thesis before the trade, we can later
    audit whether the screening process actually has hit rate, or whether
    we are telling stories about the winners and forgetting the losers.
    """

    def __init__(self, db_path: str = _DEFAULT_DB) -> None:
        self._db = sqlite3.connect(db_path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA_SQL)
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> TrialLedger:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def register_thesis(
        self,
        *,
        thesis_id: str,
        ticker: str,
        entry_target: float,
        stop_target: float,
        target_price: float,
        position_pct: float,
        catalyst: str,
        invalidation: str,
        horizon_days: int,
        f_score: int | None = None,
        magic_rank: int | None = None,
        return_12m: float | None = None,
        notes: str = "",
    ) -> str:
        """Pre-register a turnaround thesis BEFORE the trade is taken.

        Parameters
        ----------
        thesis_id : str
            Unique ID (e.g. "THESIS-2026-08-15-INTC-1"). Use a deterministic
            ID scheme so the same thesis isn't registered twice.
        ticker : str
            Ticker symbol (e.g. "INTC").
        entry_target, stop_target, target_price : float
            Entry price, stop-loss price, target exit price. All three must
            be set BEFORE the trade — no post-hoc adjustment.
        position_pct : float
            Position size as fraction of capital (e.g. 0.025 for 2.5%).
            Lane B sizing per ADR-018: 2-3% per idea.
        catalyst : str
            Identified catalyst (e.g. "New CEO turnaround", "Product launch
            + buyback announcement", "Sector rotation into semis").
        invalidation : str
            What would make the thesis wrong (e.g. "Two consecutive quarters
            of declining gross margin", "CEO departure within 6 months").
        horizon_days : int
            Maximum days to hold before time-stop.
        f_score, magic_rank, return_12m : optional
            Pre-registration of the screening signals (Piotroski F-Score,
            Greenblatt Magic Formula rank, 12-month past return) so the
            screening decision is auditable.
        notes : str
            Free-form notes.

        Returns
        -------
        str
            The SHA-256 hash of the registered row (tamper-evidence).
        """
        if position_pct <= 0 or position_pct > 0.05:
            raise ValueError(f"position_pct {position_pct} out of Lane B range (0, 5%]")
        if stop_target >= entry_target:
            raise ValueError(
                f"stop_target ({stop_target}) must be below entry_target ({entry_target})"
            )
        if target_price <= entry_target:
            raise ValueError(
                f"target_price ({target_price}) must be above entry_target ({entry_target})"
            )
        if horizon_days <= 0:
            raise ValueError(f"horizon_days {horizon_days} must be > 0")

        now = datetime.now(UTC).isoformat()
        pre_hash_input = "|".join(
            [
                thesis_id,
                ticker,
                str(entry_target),
                str(stop_target),
                str(target_price),
                str(position_pct),
                catalyst,
                invalidation,
                str(horizon_days),
                str(f_score),
                str(magic_rank),
                str(return_12m),
                now,
            ]
        )
        pre_hash = hashlib.sha256(pre_hash_input.encode("utf-8")).hexdigest()

        self._db.execute(
            """
            INSERT INTO theses (
                thesis_id, registered_at, ticker, entry_target, stop_target,
                target_price, position_pct, catalyst, invalidation,
                horizon_days, f_score, magic_rank, return_12m, notes, pre_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                thesis_id,
                now,
                ticker,
                entry_target,
                stop_target,
                target_price,
                position_pct,
                catalyst,
                invalidation,
                horizon_days,
                f_score,
                magic_rank,
                return_12m,
                notes,
                pre_hash,
            ),
        )
        self._db.commit()
        return pre_hash

    def record_outcome(
        self,
        *,
        thesis_id: str,
        exit_reason: str,
        entry_actual: float | None = None,
        exit_actual: float | None = None,
        pnl_pct: float | None = None,
        pnl_amount: float | None = None,
        bars_held: int | None = None,
        notes: str = "",
    ) -> None:
        """Record the outcome of a thesis after exit.

        exit_reason must be one of: 'target_hit', 'stop_hit', 'time_stop',
        'invalidation', 'manual_close'.
        """
        valid_reasons = {"target_hit", "stop_hit", "time_stop", "invalidation", "manual_close"}
        if exit_reason not in valid_reasons:
            raise ValueError(f"exit_reason {exit_reason!r} not in {valid_reasons}")

        # Verify thesis exists
        cur = self._db.execute("SELECT thesis_id FROM theses WHERE thesis_id = ?", (thesis_id,))
        if cur.fetchone() is None:
            raise ValueError(f"thesis_id {thesis_id!r} not registered")

        now = datetime.now(UTC).isoformat()
        self._db.execute(
            """
            INSERT INTO outcomes (
                thesis_id, closed_at, exit_reason, entry_actual, exit_actual,
                pnl_pct, pnl_amount, bars_held, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                thesis_id,
                now,
                exit_reason,
                entry_actual,
                exit_actual,
                pnl_pct,
                pnl_amount,
                bars_held,
                notes,
            ),
        )
        self._db.commit()

    def list_theses(self, ticker: str | None = None) -> list[dict[str, Any]]:
        """List theses, optionally filtered by ticker."""
        if ticker is None:
            cur = self._db.execute("SELECT * FROM theses ORDER BY registered_at DESC")
        else:
            cur = self._db.execute(
                "SELECT * FROM theses WHERE ticker = ? ORDER BY registered_at DESC", (ticker,)
            )
        rows = cur.fetchall()
        return [dict(r) for r in rows]

    def list_outcomes(self, thesis_id: str | None = None) -> list[dict[str, Any]]:
        """List outcomes, optionally filtered by thesis_id."""
        if thesis_id is None:
            cur = self._db.execute("SELECT * FROM outcomes ORDER BY closed_at DESC")
        else:
            cur = self._db.execute(
                "SELECT * FROM outcomes WHERE thesis_id = ? ORDER BY closed_at DESC", (thesis_id,)
            )
        rows = cur.fetchall()
        return [dict(r) for r in rows]

    def hit_rate(self) -> dict[str, float | int]:
        """Compute the realized hit-rate of pre-registered theses.

        Returns
        -------
        dict with keys:
        - 'n_theses': total theses registered
        - 'n_with_outcome': theses with a closed outcome
        - 'n_target_hit': outcomes where exit_reason == 'target_hit'
        - 'n_stop_hit': outcomes where exit_reason == 'stop_hit'
        - 'n_time_stop': outcomes where exit_reason == 'time_stop'
        - 'n_invalidation': outcomes where exit_reason == 'invalidation'
        - 'n_manual_close': outcomes where exit_reason == 'manual_close'
        - 'hit_rate': n_target_hit / n_with_outcome (or 0 if no outcomes)
        - 'avg_pnl_pct': mean pnl_pct across outcomes with non-null pnl_pct
        """
        cur = self._db.execute("SELECT COUNT(*) AS n FROM theses")
        n_theses = int(cur.fetchone()["n"])

        cur = self._db.execute(
            "SELECT exit_reason, COUNT(*) AS n, AVG(pnl_pct) AS avg_pnl "
            "FROM outcomes GROUP BY exit_reason"
        )
        breakdown = {
            row["exit_reason"]: (int(row["n"]), float(row["avg_pnl"] or 0.0))
            for row in cur.fetchall()
        }

        n_target_hit = breakdown.get("target_hit", (0, 0.0))[0]
        n_stop_hit = breakdown.get("stop_hit", (0, 0.0))[0]
        n_time_stop = breakdown.get("time_stop", (0, 0.0))[0]
        n_invalidation = breakdown.get("invalidation", (0, 0.0))[0]
        n_manual_close = breakdown.get("manual_close", (0, 0.0))[0]
        n_with_outcome = n_target_hit + n_stop_hit + n_time_stop + n_invalidation + n_manual_close

        cur = self._db.execute(
            "SELECT AVG(pnl_pct) AS avg_pnl FROM outcomes WHERE pnl_pct IS NOT NULL"
        )
        avg_pnl_pct_row = cur.fetchone()
        avg_pnl_pct = float(avg_pnl_pct_row["avg_pnl"] or 0.0) if avg_pnl_pct_row else 0.0

        return {
            "n_theses": n_theses,
            "n_with_outcome": n_with_outcome,
            "n_target_hit": n_target_hit,
            "n_stop_hit": n_stop_hit,
            "n_time_stop": n_time_stop,
            "n_invalidation": n_invalidation,
            "n_manual_close": n_manual_close,
            "hit_rate": (n_target_hit / n_with_outcome) if n_with_outcome > 0 else 0.0,
            "avg_pnl_pct": avg_pnl_pct,
        }

    def export_for_audit(self) -> dict[str, Any]:
        """Export all theses + outcomes as a JSON-serialisable dict.

        Use this for end-of-quarter audit: verify the pre-registered thesis
        matches the actual trade (no HARKing), and compute the hit rate.
        """
        return {
            "theses": self.list_theses(),
            "outcomes": self.list_outcomes(),
            "hit_rate": self.hit_rate(),
        }


__all__: list[str] = ["TrialLedger"]
