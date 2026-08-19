"""Test del modello economico eval prop-firm (BL-094, scripts/run_eval_economics.py)."""

from __future__ import annotations

import pytest

from scripts.run_eval_economics import (
    accounts_required,
    alpha_required_single,
    attempts_for_p90,
    simulate_pass_probability,
)

N = 8_000  # n_sims nei test: veloce e sufficiente per le tolleranze sotto


@pytest.mark.parametrize(
    ("alpha", "sigma", "lo", "hi"),
    [
        # Zero drift, barrier 6%/4% EOD trailing (ratchet): p ~30% a sigma 1.2%
        # (sotto la parity a barriere fisse B/(A+B)=40%: il ratchet segue i massimi)
        (0.00, 0.012, 0.27, 0.33),
        # L'alpha misurato (+6% lordo) sposta il pass-rate di pochi punti
        (0.06, 0.012, 0.30, 0.37),
        # Vol alta + alpha: resta un coin flip
        (0.06, 0.016, 0.31, 0.38),
    ],
)
def test_pass_probability_sanity(alpha: float, sigma: float, lo: float, hi: float) -> None:
    res = simulate_pass_probability(alpha, sigma, n_sims=N, seed=7)
    assert lo < res["p_pass"] < hi
    # Esiti mutuamente esclusivi (primo evento chiude la path)
    assert res["p_pass"] + res["p_breach"] + res["p_neither"] == pytest.approx(1.0)


def test_low_sigma_with_drift_is_high_pass_rate() -> None:
    # Leva vera = rischio per-trade: sigma basso + drift alto → pass rate alto
    res = simulate_pass_probability(0.12, 0.004, n_sims=N, seed=11)
    assert res["p_pass"] > 0.70


def test_deterministic_seed() -> None:
    a = simulate_pass_probability(0.06, 0.012, seed=42)
    b = simulate_pass_probability(0.06, 0.012, seed=42)
    assert a == b


def test_accounts_required_reference_case() -> None:
    # 6% alpha, split 90%, 150K: €3K/mese netti → ~6.6 account (check calcolato a mano)
    n = accounts_required(split=0.9, alpha=0.06, account_size=150_000)
    assert abs(n - 6.6) < 0.5


def test_accounts_required_scaling() -> None:
    n50 = accounts_required(split=0.9, alpha=0.06, account_size=50_000)
    n200 = accounts_required(split=0.9, alpha=0.06, account_size=200_000)
    assert n50 > n200 > 0
    assert alpha_required_single(split=0.9, account_size=150_000) < alpha_required_single(
        split=0.8, account_size=50_000
    )


def test_attempts_for_p90() -> None:
    assert attempts_for_p90(0.4) == 5  # ln(.1)/ln(.6) = 4.5 → ceil 5
    assert attempts_for_p90(0.44) == 4
    assert attempts_for_p90(1.0) == 1
