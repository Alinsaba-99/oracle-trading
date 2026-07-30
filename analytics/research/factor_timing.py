"""BL-091 — Factor Timing Engine: IC ranking + decay detection.

Computes per-specialist Information Coefficient (IC) from historical
decisions stored in ResearchMemory. Uses a rolling window of past
decisions to measure which specialists are currently effective.

Pattern inspired by Inalpha's effectiveness.py (Rank IC + ICIR + decay state).

Rank IC = Spearman rank correlation between predicted signal direction
(-1, 0, 1) and actual P&L outcome. A positive IC means the specialist's
signal direction correlates with profitable outcomes.

Decay state compares recent IC (last 1/3 of window) against full-window IC:
  - "stable": recent IC same sign and ≥60% magnitude of full IC
  - "fading": recent IC same sign but weaker
  - "decaying": recent IC opposite sign or zero (specialist losing edge)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger("oracle.research.factor_timing")

# Minimum observations required for a meaningful IC calculation
_MIN_OBS = 8
# IC threshold for positive direction signal
_IC_DIRECTION_THRESHOLD = 0.02
# Full-strength IC magnitude (normalization denominator for IC → weight mapping)
_IC_FULL_STRENGTH = 0.05
# Fraction of window considered "recent" for decay detection
_RECENT_FRACTION = 3
# Retention ratio below which a stable factor is called fading
_DECAY_STABLE_RETENTION = 0.6


@dataclass(frozen=True, slots=True)
class FactorTimingResult:
    """IC score and decay state for one specialist.

    Attributes:
        specialist: Specialist identifier (e.g. "trend", "mean_rev").
        rank_ic: Spearman rank IC over the full window.
        rank_ic_recent: Rank IC over the most recent 1/3 of observations.
        icir: Information Coefficient Information Ratio (mean IC / std IC
              across sub-windows). Measures consistency of the signal.
        win_rate: Fraction of decisions with positive P&L.
        mean_pnl: Average P&L per decision in account currency.
        n: Number of observations used.
        direction: +1 if IC > threshold, -1 if IC < -threshold, 0 otherwise.
        strength: Normalized IC magnitude [0, 1].
        decay_state: "stable", "fading", or "decaying".
        weight: Recommended allocation weight [0, 1] for this specialist.
    """

    specialist: str
    rank_ic: float
    rank_ic_recent: float
    icir: float
    win_rate: float
    mean_pnl: float
    n: int
    direction: int
    strength: float
    decay_state: str
    weight: float


# ---------------------------------------------------------------------------
# Rank IC calculation
# ---------------------------------------------------------------------------


def _spearman_rank_ic(signals: np.ndarray, pnls: np.ndarray) -> float:
    """Compute Spearman rank IC between signal direction and P&L.

    Args:
        signals: Array of signal values (-1, 0, 1).
        pnls: Array of corresponding P&L outcomes.

    Returns:
        Spearman rank correlation coefficient [−1, 1].
    """
    if len(signals) < _MIN_OBS or len(pnls) < _MIN_OBS:
        return 0.0
    # Guard against constant arrays (variance = 0) that produce NaN correlation
    if np.std(signals) == 0 or np.std(pnls) == 0:
        return 0.0
    # Convert to ranks
    from scipy.stats import rankdata

    sig_ranks = rankdata(signals)
    pnl_ranks = rankdata(pnls)
    # Pearson correlation on ranks = Spearman
    r = np.corrcoef(sig_ranks, pnl_ranks)
    if r.size >= 4:
        val = float(r[0, 1])
        return val if np.isfinite(val) else 0.0
    return 0.0


def _compute_icir(ics: list[float]) -> float:
    """Information Coefficient Information Ratio.

    ICIR = mean(IC) / std(IC).  High positive ICIR means the specialist
    consistently predicts in the right direction.  Negative or near-zero
    ICIR means the signal is noise.
    """
    if len(ics) < 3:
        return 0.0
    mean_ic = float(np.mean(ics))
    std_ic = float(np.std(ics, ddof=1)) or 1e-9
    return mean_ic / std_ic


def _decay_state(rank_ic: float, rank_ic_recent: float) -> str:
    """Classify factor decay into stable / fading / decaying.

    Args:
        rank_ic: Full-window Rank IC.
        rank_ic_recent: Rank IC over the most recent 1/3 of data.

    Returns:
        One of "stable", "fading", "decaying".
    """
    if rank_ic_recent == 0.0 or np.sign(rank_ic_recent) != np.sign(rank_ic):
        return "decaying"
    if abs(rank_ic_recent) >= _DECAY_STABLE_RETENTION * abs(rank_ic):
        return "stable"
    return "fading"


def _ic_weight(rank_ic: float, decay_state: str) -> float:
    """Map IC + decay state to a recommended allocation weight [0, 1].

    Positive IC → weight proportional to strength.
    Negative IC → zero weight (anti-signal).
    Decaying factors are penalised.
    """
    if rank_ic <= 0:
        return 0.0
    raw = min(1.0, abs(rank_ic) / _IC_FULL_STRENGTH)
    if decay_state == "decaying":
        raw *= 0.3
    elif decay_state == "fading":
        raw *= 0.7
    return round(raw, 4)


# ---------------------------------------------------------------------------
# Factor Timing Engine
# ---------------------------------------------------------------------------


def compute_factor_timing(
    decisions: list[dict[str, Any]], window: int = 100
) -> list[FactorTimingResult]:
    """Compute per-specialist IC scores and decay states.

    Args:
        decisions: List of decision dicts from ResearchMemory
            (must contain "specialist", "pnl", optionally "signal").
            P&L must be recorded (non-None).
        window: Max number of most-recent decisions to use per specialist.

    Returns:
        Sorted list of FactorTimingResult, highest weight first.
    """
    # Group decisions by specialist, filter to those with P&L
    by_spec: dict[str, list[dict[str, Any]]] = {}
    for d in decisions:
        pnl = d.get("pnl")
        if pnl is None:
            continue
        spec = d.get("specialist", "unknown")
        by_spec.setdefault(spec, []).append(d)

    results: list[FactorTimingResult] = []
    for specialist, specs in by_spec.items():
        # Take most recent N
        recent = specs[-window:]
        if len(recent) < _MIN_OBS:
            logger.debug("Skip %s: only %d obs (need %d)", specialist, len(recent), _MIN_OBS)
            continue

        n = len(recent)
        signals = np.array([float(d.get("signal", 0) or 0) for d in recent])
        pnls = np.array([float(d["pnl"]) for d in recent])
        win_rate = float(np.mean(pnls > 0))
        mean_pnl = float(np.mean(pnls))

        # Full-window Rank IC
        rank_ic = _spearman_rank_ic(signals, pnls)

        # Recent-window Rank IC (last 1/3)
        split = n // _RECENT_FRACTION
        recent_pnls = pnls[-split:] if split >= _MIN_OBS else pnls
        recent_signals = signals[-split:] if split >= _MIN_OBS else signals
        rank_ic_recent = _spearman_rank_ic(recent_signals, recent_pnls)

        # ICIR: split window into 5 segments, compute IC per segment
        seg_size = max(_MIN_OBS, n // 5)
        seg_ics: list[float] = []
        for j in range(0, n - seg_size + 1, seg_size):
            seg_sigs = signals[j : j + seg_size]
            seg_pnls = pnls[j : j + seg_size]
            if len(seg_sigs) >= _MIN_OBS:
                seg_ics.append(_spearman_rank_ic(seg_sigs, seg_pnls))
        icir = _compute_icir(seg_ics)

        # Direction and strength
        direction = (
            1
            if rank_ic > _IC_DIRECTION_THRESHOLD
            else -1
            if rank_ic < -_IC_DIRECTION_THRESHOLD
            else 0
        )
        strength = min(1.0, abs(rank_ic) / _IC_FULL_STRENGTH)

        # Decay state
        state = _decay_state(rank_ic, rank_ic_recent)
        weight = _ic_weight(rank_ic, state)

        results.append(
            FactorTimingResult(
                specialist=specialist,
                rank_ic=round(rank_ic, 4),
                rank_ic_recent=round(rank_ic_recent, 4),
                icir=round(icir, 4),
                win_rate=round(win_rate, 4),
                mean_pnl=round(mean_pnl, 4),
                n=n,
                direction=direction,
                strength=round(strength, 4),
                decay_state=state,
                weight=weight,
            )
        )

    results.sort(key=lambda r: r.weight, reverse=True)
    return results


def format_timing_report(results: list[FactorTimingResult]) -> str:
    """Return a human-readable table of factor timing results."""
    if not results:
        return "  (no specialists with sufficient data)\n"
    lines = [
        "  Specialist        IC     IC_rec   ICIR   WR%   Mean$   N  Decay      Wt",
        "  " + "-" * 75,
    ]
    for r in results:
        decay_mark = {"stable": "🟢", "fading": "🟡", "decaying": "🔴"}.get(r.decay_state, "⚪")
        lines.append(
            f"  {r.specialist:<16s} "
            f"{r.rank_ic:>+6.3f} {r.rank_ic_recent:>+6.3f} "
            f"{r.icir:>+6.3f} {r.win_rate:>5.1%} "
            f"{r.mean_pnl:>+7.2f} {r.n:>3d}  "
            f"{decay_mark} {r.decay_state:<8s} {r.weight:.2f}"
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Direct computation from signal + return arrays (no ResearchMemory needed)
# ---------------------------------------------------------------------------


def compute_per_session_ic(
    signal_series: np.ndarray, equity_curve: list[float], specialist: str = "ensemble"
) -> FactorTimingResult:
    """Compute IC for a single session from signal and equity series.

    Args:
        signal_series: Per-bar signal array (-1, 0, 1 values), shape (N_bars,).
        equity_curve: Per-bar equity curve, length N_bars + 1 (initial equity
            followed by N_bars equity values).
        specialist: Specialist label to attach to the result.

    Returns:
        FactorTimingResult with IC and decay state, or None if insufficient data.
    """
    if len(signal_series) < _MIN_OBS or len(equity_curve) < _MIN_OBS + 1:
        return FactorTimingResult(
            specialist=specialist,
            rank_ic=0.0,
            rank_ic_recent=0.0,
            icir=0.0,
            win_rate=0.0,
            mean_pnl=0.0,
            n=0,
            direction=0,
            strength=0.0,
            decay_state="unknown",
            weight=0.0,
        )

    # Per-bar return from equity curve
    n = min(len(signal_series), len(equity_curve) - 1)
    signals = signal_series[:n].astype(float)
    pnls = np.array([equity_curve[k] - equity_curve[k - 1] for k in range(1, n + 1)])

    # Rank IC
    rank_ic = _spearman_rank_ic(signals, pnls)

    # Recent IC (last 1/3)
    split = max(_MIN_OBS, n // _RECENT_FRACTION)
    rank_ic_recent = _spearman_rank_ic(signals[-split:], pnls[-split:])

    # ICIR over segments
    seg_size = max(_MIN_OBS, n // 5)
    seg_ics: list[float] = []
    for j in range(0, n - seg_size + 1, seg_size):
        sigs = signals[j : j + seg_size]
        ps = pnls[j : j + seg_size]
        if len(sigs) >= _MIN_OBS:
            seg_ics.append(_spearman_rank_ic(sigs, ps))
    icir = _compute_icir(seg_ics)
    win_rate = float(np.mean(pnls > 0))
    mean_pnl = float(np.mean(pnls))

    direction = (
        1 if rank_ic > _IC_DIRECTION_THRESHOLD else -1 if rank_ic < -_IC_DIRECTION_THRESHOLD else 0
    )
    strength = min(1.0, abs(rank_ic) / _IC_FULL_STRENGTH)
    state = _decay_state(rank_ic, rank_ic_recent)
    weight = _ic_weight(rank_ic, state)

    return FactorTimingResult(
        specialist=specialist,
        rank_ic=round(rank_ic, 4),
        rank_ic_recent=round(rank_ic_recent, 4),
        icir=round(icir, 4),
        win_rate=round(win_rate, 4),
        mean_pnl=round(mean_pnl, 4),
        n=n,
        direction=direction,
        strength=round(strength, 4),
        decay_state=state,
        weight=weight,
    )


def update_factor_timing_in_memory(
    memory: Any,  # ResearchMemory
    window: int = 100,
) -> list[FactorTimingResult]:
    """Read from ResearchMemory, compute IC, and store results back.

    This is the main entry-point.  Call it at the end of each paper session.

    Args:
        memory: ``ResearchMemory`` instance.
        window: Rolling window for IC calculation.

    Returns:
        Factor timing results sorted by weight descending.
    """
    decisions = memory.get_recent_decisions(n=window * 5)  # generous buffer
    results = compute_factor_timing(decisions, window=window)
    # Store IC scores in the memory (can be retrieved later for weighting)
    _persist_ic_scores(memory, results)
    return results


def _persist_ic_scores(memory: Any, results: list[FactorTimingResult]) -> None:
    """Store IC scores into ResearchMemory's metadata table."""

    try:
        memory._conn.execute(
            "CREATE TABLE IF NOT EXISTS factor_ic ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  timestamp TEXT NOT NULL,"
            "  specialist TEXT NOT NULL,"
            "  rank_ic REAL,"
            "  rank_ic_recent REAL,"
            "  icir REAL,"
            "  win_rate REAL,"
            "  mean_pnl REAL,"
            "  decay_state TEXT,"
            "  weight REAL"
            ")"
        )
        from datetime import UTC, datetime

        now = datetime.now(UTC).isoformat()
        for r in results:
            memory._conn.execute(
                "INSERT INTO factor_ic "
                "(timestamp, specialist, rank_ic, rank_ic_recent, icir, "
                " win_rate, mean_pnl, decay_state, weight) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    now,
                    r.specialist,
                    r.rank_ic,
                    r.rank_ic_recent,
                    r.icir,
                    r.win_rate,
                    r.mean_pnl,
                    r.decay_state,
                    r.weight,
                ),
            )
        memory._conn.commit()
    except Exception as exc:
        logger.warning("Failed to persist IC scores: %s", exc)


def get_latest_ic_weights(memory: Any) -> dict[str, float]:
    """Return the latest IC-based weight per specialist.

    Args:
        memory: ``ResearchMemory`` instance.

    Returns:
        Dict mapping specialist name → weight [0, 1].
    """
    try:
        rows = memory._conn.execute(
            "SELECT specialist, weight FROM factor_ic "
            "WHERE id IN (SELECT MAX(id) FROM factor_ic GROUP BY specialist)"
        ).fetchall()
        return {r["specialist"]: float(r["weight"]) for r in rows}
    except Exception:
        return {}


__all__ = [
    "FactorTimingResult",
    "compute_factor_timing",
    "format_timing_report",
    "get_latest_ic_weights",
    "update_factor_timing_in_memory",
]
