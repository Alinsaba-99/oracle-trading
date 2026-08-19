"""Test del simulatore eval empirico (BL-094, scripts/run_eval_simulation.py)."""

from __future__ import annotations

import numpy as np

from scripts.run_eval_simulation import (
    OUTCOME_BREACH,
    OUTCOME_DAILY_LOSS,
    OUTCOME_NO_TRADES,
    OUTCOME_PASS,
    OUTCOME_TIMEOUT,
    eval_day_pnl,
    generate_attempt_starts,
    run_signal_eval,
    simulate_eval_attempt,
    wilson_ci,
)


def _uptrend(n: int = 1000, start: float = 1000.0, daily: float = 0.0007) -> np.ndarray:
    return start * (1.0 + daily) ** np.arange(n)


def _downtrend(n: int = 1000, start: float = 1000.0, daily: float = -0.0007) -> np.ndarray:
    return start * (1.0 + daily) ** np.arange(n)


def _ones(n: int) -> np.ndarray:
    return np.ones(n, dtype=np.float64)


# --- eval_day_pnl: sizing e costi -------------------------------------------


def test_day_pnl_sizing_and_costs() -> None:
    # 1 pt x $50 = $50/giorno; entry -$4.2, exit -$4.2; posizione da prima
    pnl = eval_day_pnl(np.array([1.0, 0.0]), np.array([1.0, 0.0]))
    np.testing.assert_allclose(pnl, [45.8, -4.2])
    # Flat al primo giorno: nessun P&L il giorno 0; entry (cambio 0->1) al giorno 1
    pnl2 = eval_day_pnl(np.array([0.0, 1.0]), np.array([1.0, 1.0]))
    np.testing.assert_allclose(pnl2, [0.0, 45.8])
    # Posizione continua: nessun costo
    pnl3 = eval_day_pnl(np.array([1.0, 1.0, 1.0]), np.array([1.0, 1.0, 1.0]))
    np.testing.assert_allclose(pnl3, [45.8, 50.0, 50.0])


# --- simulate_eval_attempt: esiti -------------------------------------------


def test_uptrend_passes() -> None:
    closes = _uptrend()
    res = simulate_eval_attempt(_ones(len(closes)), closes, start=250)
    assert res["outcome"] == OUTCOME_PASS
    assert res["days"] < 200


def test_downtrend_breaches() -> None:
    closes = _downtrend()
    res = simulate_eval_attempt(_ones(len(closes)), closes, start=250)
    assert res["outcome"] == OUTCOME_BREACH


def test_no_trades_outcome() -> None:
    closes = _uptrend()
    res = simulate_eval_attempt(np.zeros(len(closes)), closes, start=250)
    assert res["outcome"] == OUTCOME_NO_TRADES


def test_consistency_blocks_first_touch_then_dilutes() -> None:
    # L'attempt parte a barra 250 (posizione dal close[249]): il giorno di
    # +60pt (target 3000 in un colpo) deve stare DENTRO la finestra -> a barra 250.
    # best_day > 50% del total -> touch bloccato; poi +1pt/giorno serve a
    # diluire finche' total >= 6000 (best_day <= 50%).
    closes = np.concatenate([np.full(250, 1000.0), [1060.0], 1060.0 + np.arange(1.0, 500.0)])
    res = simulate_eval_attempt(_ones(len(closes)), closes, start=250)
    assert res["outcome"] == OUTCOME_PASS
    assert res["blocked_before"] is True
    assert res["days"] > 60  # ha dovuto diluire
    # Con finestra corta: il touch bloccato non passa e scade
    res_short = simulate_eval_attempt(_ones(len(closes)), closes, start=250, max_bars=30)
    assert res_short["outcome"] == OUTCOME_TIMEOUT


def test_daily_loss_outcome_when_enabled() -> None:
    # Giorno di -30pt a barra 250: trailing breach a -40pt non ancora, daily loss
    # 2% = -$1.000 si (1 contratto ES: -30pt x $50 = -$1.500).
    closes = np.concatenate([np.full(250, 1000.0), [970.0], np.full(500, 970.0)])
    res = simulate_eval_attempt(_ones(len(closes)), closes, start=250, daily_loss_frac=0.02)
    assert res["outcome"] == OUTCOME_DAILY_LOSS
    # Stessa serie senza daily loss: nessun breach (-1500 > -2000) -> timeout
    res_no = simulate_eval_attempt(_ones(len(closes)), closes, start=250, daily_loss_frac=0.0)
    assert res_no["outcome"] == OUTCOME_TIMEOUT


def test_target_and_breach_order() -> None:
    # Dalla barra 250: +1pt/giorno fino a +61pt (il target 3000 netto di entry
    # cost arriva al giorno 60), poi crollo sotto il trailing: pass prima di breach.
    closes = np.concatenate(
        [np.full(250, 1000.0), 1000.0 + np.arange(1.0, 62.0), np.full(400, 990.0)]
    )
    res = simulate_eval_attempt(_ones(len(closes)), closes, start=250)
    assert res["outcome"] == OUTCOME_PASS


# --- aggregazione walk-forward ----------------------------------------------


def test_run_signal_eval_uptrend_all_pass() -> None:
    closes = _uptrend()
    agg = run_signal_eval(_ones(len(closes)), closes)
    assert agg["p_pass"] == 1.0
    assert agg["attempts"] == len(generate_attempt_starts(len(closes)))
    assert agg["n_breach"] == 0


def test_generate_attempt_starts() -> None:
    starts = generate_attempt_starts(1000, warmup=250, step=63, min_bars=60)
    assert starts == list(range(250, 940, 63))
    assert len(starts) == 11


def test_wilson_ci_sanity() -> None:
    lo, hi = wilson_ci(34, 100)
    assert lo < 0.34 < hi
    assert wilson_ci(0, 0) == (0.0, 0.0)
