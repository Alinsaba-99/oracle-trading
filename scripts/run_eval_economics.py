"""S0.2 (BL-094) — Modello economico prop-firm: probabilità di passare l'eval.

Monte Carlo del percorso eval (profit target 6%, trailing max loss 4% EOD,
returns giornalieri iid gaussiani) per stimare p(pass), giorni attesi a
passare e tentativi attesi, in funzione di alpha (drift annuale, NETTO dei
costi di trading) e volatilità daily.

Aggiunge la tabella deterministica dei requisiti di scala per €3K/mese
netti (tasse 26% IT, EUR/USD 1.10, split 80-90%) — il deliverable di BL-094.

Vincoli di input dal repo:
- alpha di riferimento = +2.3%..+6.1% lordo (autopsia S0.1, docs/reports/s0-1-bl023-autopsy.md)
- eval 50K 2026: target $3,000 (6%), trailing MLL $2,000 (4%) — fonti web
  2026-08 (da riconfermare con snapshot hash in S0.5).

Uso:
    uv run python scripts/run_eval_economics.py [--n-sims 10000]
        [--out docs/reports/s0-2/eval_economics.json]
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

TRADING_DAYS = 252
TARGET_FRAC = 0.06  # +6% profit target su 50K (MFF Core/Pro, Topstep TC 2026)
MAX_LOSS_FRAC = 0.04  # trailing EOD 4% su 50K

GRID_ALPHAS = (0.00, 0.02, 0.04, 0.06, 0.12)  # drift annuale netto costi trading
GRID_SIGMAS = (0.004, 0.008, 0.012, 0.016)  # vol daily (ES 1d ~1.2%)

# Requisiti scala (tabelle deterministiche)
NET_MONTHLY_TARGET_EUR = 3000
TAX_RATE = 0.26  # capital gains IT su payout futures
FX_EUR_USD = 1.10
SPLITS = (0.8, 0.9)
ACCOUNT_SIZES = (50_000, 100_000, 150_000, 200_000)
TABLE_ALPHAS = (0.02, 0.04, 0.06)

# Fee (fonti web 2026-08, da riconfermare in S0.5)
MFF_BUILDER_FEE_USD = 153  # one-time, 50K (default MLL $2,000)
TOPSTEP_MONTHLY_FEE_USD = 49  # TC 50K, subscription
TOPSTEP_ACTIVATION_FEE_USD = 149


def simulate_pass_probability(
    alpha: float,
    sigma: float,
    *,
    target_frac: float = TARGET_FRAC,
    max_loss_frac: float = MAX_LOSS_FRAC,
    n_sims: int = 10_000,
    max_days: int = 1500,
    seed: int = 42,
) -> dict[str, float]:
    """Probabilità di hit del profit target prima del trailing breach (MC daily).

    Returns (in trading days, +1 = indice giorno):
        p_pass / p_breach / p_neither: probabilità di esito
        mean/median/p90_days_to_pass: statistiche sui sims che passano
    """
    rng = np.random.default_rng(seed)
    mu = alpha / TRADING_DAYS
    steps = rng.normal(mu, sigma, size=(n_sims, max_days))
    balance = 1.0 + np.cumsum(steps, axis=1)
    hwm = np.maximum.accumulate(balance, axis=1)

    pass_mask = balance >= 1.0 + target_frac
    breach_mask = balance < hwm * (1.0 - max_loss_frac)

    first_pass = np.argmax(pass_mask, axis=1)
    first_breach = np.argmax(breach_mask, axis=1)
    did_pass = pass_mask.any(axis=1)
    did_breach = breach_mask.any(axis=1)
    pass_first = did_pass & ((~did_breach) | (first_pass < first_breach))
    # Esiti mutualmente esclusivi: il primo evento chiude l'outcome della path
    breach_first = did_breach & (~did_pass | (first_breach < first_pass))

    passed = pass_first.sum()
    days_to_pass = first_pass[pass_first] + 1

    result: dict[str, float] = {
        "p_pass": float(passed / n_sims),
        "p_breach": float(breach_first.sum() / n_sims),
        "p_neither": float((~pass_first & ~breach_first).sum() / n_sims),
    }
    if passed:
        result["mean_days_to_pass"] = float(days_to_pass.mean())
        result["median_days_to_pass"] = float(np.median(days_to_pass))
        result["p90_days_to_pass"] = float(np.percentile(days_to_pass, 90))
    return result


def accounts_required(
    *,
    split: float,
    alpha: float,
    account_size: float,
    net_monthly_eur: float = NET_MONTHLY_TARGET_EUR,
    tax_rate: float = TAX_RATE,
    fx: float = FX_EUR_USD,
) -> float:
    """Numero di account funded concorrenti per €net_monthly/mese.

    gross_trader_usd = target netto annuo pre-tassa in USD, ricevuto dal
    trader; ogni account rende split x alpha x size.
    """
    gross_trader_usd = net_monthly_eur * 12 * fx / (1.0 - tax_rate)
    per_account_usd = split * alpha * account_size
    return gross_trader_usd / per_account_usd


def alpha_required_single(
    *,
    split: float,
    account_size: float,
    net_monthly_eur: float = NET_MONTHLY_TARGET_EUR,
    tax_rate: float = TAX_RATE,
    fx: float = FX_EUR_USD,
) -> float:
    """Alpha annuale lordo richiesto su UN account per €net_monthly/mese."""
    gross_trader_usd = net_monthly_eur * 12 * fx / (1.0 - tax_rate)
    return gross_trader_usd / (split * account_size)


def attempts_for_p90(p_pass: float) -> int:
    """Tentativi eval per avere >=90% di vederne passare almeno uno."""
    if p_pass >= 1.0:
        return 1
    return math.ceil(math.log(0.1) / math.log(1.0 - p_pass))


def build_results(n_sims: int, seed: int) -> dict[str, Any]:
    mc_results = [
        {
            "alpha": alpha,
            "sigma": sigma,
            **simulate_pass_probability(alpha, sigma, n_sims=n_sims, seed=seed),
        }
        for alpha in GRID_ALPHAS
        for sigma in GRID_SIGMAS
    ]

    accounts_table = [
        {
            "split": split,
            "account_size": size,
            "alpha_required_single_account": round(
                alpha_required_single(split=split, account_size=size), 4
            ),
            "accounts_at_alpha": {
                f"{a:.0%}": round(accounts_required(split=split, alpha=a, account_size=size), 2)
                for a in TABLE_ALPHAS
            },
        }
        for split in SPLITS
        for size in ACCOUNT_SIZES
    ]

    attempts = [
        {"p_pass": p, "expected_attempts": round(1.0 / p, 2), "p90_attempts": attempts_for_p90(p)}
        for p in sorted({row["p_pass"] for row in mc_results}, reverse=True)
    ]

    return {
        "schema": "s0-2-eval-economics-v1",
        "generated_by": "scripts/run_eval_economics.py",
        "date": date.today().isoformat(),
        "params": {
            "target_frac": TARGET_FRAC,
            "max_loss_frac": MAX_LOSS_FRAC,
            "trading_days": TRADING_DAYS,
            "n_sims": n_sims,
            "max_days": 1500,
            "seed": seed,
            "net_monthly_target_eur": NET_MONTHLY_TARGET_EUR,
            "tax_rate": TAX_RATE,
            "fx_eur_usd": FX_EUR_USD,
        },
        "monte_carlo": mc_results,
        "accounts_table": accounts_table,
        "attempts": attempts,
    }


def _print_mc(results: dict[str, Any]) -> None:
    print("\n=== p(pass) eval 6%/4% (MC daily) ===")
    print(f"{'alpha/yr':>8} | " + " | ".join(f"sig={s:.1%}" for s in GRID_SIGMAS))
    for alpha in GRID_ALPHAS:
        row = [r for r in results["monte_carlo"] if r["alpha"] == alpha]
        cells = [f"{r['p_pass']:.1%} (med {r['median_days_to_pass']:.0f}d)" for r in row]
        print(f"{alpha:>8.0%} | " + " | ".join(cells))
    print("  (med = giorni mediani a passare, solo sims che passano)")


def _print_accounts(results: dict[str, Any]) -> None:
    print("\n=== Account concorrenti per €3K/mese netti ===")
    for row in results["accounts_table"]:
        if row["split"] != 0.9:
            continue
        print(
            f"split 90% size {row['account_size']:>7,}: alpha req/account "
            f"{row['alpha_required_single_account']:.1%} | account @2/4/6%: "
            f"{row['accounts_at_alpha']['2%']}/{row['accounts_at_alpha']['4%']}/"
            f"{row['accounts_at_alpha']['6%']}"
        )


def _print_attempts(results: dict[str, Any]) -> None:
    print("\n=== Tentativi eval (P90) ===")
    for a in results["attempts"]:
        print(
            f"p={a['p_pass']:.1%}: E[tentativi]={a['expected_attempts']} "
            f"P90={a['p90_attempts']} | fee P90 MFF one-time ~"
            f"${a['p90_attempts'] * MFF_BUILDER_FEE_USD:,.0f}, Topstep ~"
            f"${a['p90_attempts'] * TOPSTEP_MONTHLY_FEE_USD + TOPSTEP_ACTIVATION_FEE_USD:,.0f}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-sims", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="docs/reports/s0-2/eval_economics.json")
    args = parser.parse_args(argv)

    results = build_results(n_sims=args.n_sims, seed=args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2) + "\n")

    _print_mc(results)
    _print_accounts(results)
    _print_attempts(results)
    print(f"\nJSON: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
