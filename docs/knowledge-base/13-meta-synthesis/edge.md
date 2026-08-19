# 13 Meta-synthesis — Edge Plausibility

> Valutazione critica per ensemble meta-synthesis.

## Edge summary

| Method | Source | Edge | Free $0 | Orizzonte | Decay |
|---|---|---|---|---|---|
| Renaissance pattern (5k signals + HRP + meta-label) | Simons 1988-2018 | Sharpe > 9 (institutional) | n/a (proprietary data + infra) | intraday-monthly | n/a |
| HRP portfolio allocation | Lopez de Prado 2016 | +1-2%/yr OOS over Markowitz | ✅ | monthly | basso |
| Meta-labeling (side vs size separation) | Lopez de Prado 2018 | +1-2%/yr Sharpe improvement | ✅ | varies | basso |
| Hamilton HMM regime switching | Hamilton 1989 | +1-2%/yr adapt to regime | ✅ | monthly | basso |
| Equal weight ensemble | baseline | simple, robust | ✅ | monthly | n/a |
| Inverse volatility weighting | risk parity | +0.5-1%/yr over equal weight | ✅ | monthly | basso |
| Stacking (secondary ML) | academic | +1-2%/yr if signals correlated | ✅ | monthly | medio (overfit risk) |
| Bayesian model averaging | academic | +0.5-1%/yr robust | ✅ | monthly | basso |

## Verdetto edge

**Edge applicabile Oracle**:
- **HRP** (Lopez de Prado 2016) — robusto OOS, no matrix inversion.
- **Meta-labeling** (Lopez de Prado 2018) — separates side from size.
- **Hamilton HMM** — regime-aware allocation.
- **Inverse volatility + signal weighting** — risk-parity across lanes.

**Edge aspirational (NON replicabile Oracle)**:
- **Renaissance Medallion Sharpe > 9** — proprietary data + 5,000 signals + HFT infrastructure. $0 Oracle non può replicare. Aspettarsi Sharpe 1.0-1.5 con 11 lanes ensemble.

## Regime dipendenza

- Meta-synthesis è **regime-aware** per construction (Hamilton HMM switches weights).
- Different lanes active in different regimes:
  - Bull: Lane B + C (momentum/value) + Lane I (seasonal Halloween)
  - Bear: Lane K (behavioral Taleb barbell) + Lane D VRP (regime-filtered)
  - Recession: Lane H (intermarket flight-to-quality) + Lane G (COT defensive)
  - Expansion: Lane F (crypto L2 order flow) + Lane J (on-chain crypto cycle)

## Cost-realism check

- **Trading costs**: multi-lane ensemble, ~500-1000 trades/yr across lanes → 0.5-1.5% slippage.
- **Tax**: ETFs + futures 60/40 (US), 26% IT cap gains.
- **Net edge realistico**: +3-5%/yr post-cost su 5y con 11-lane ensemble. Sharpe 1.0-1.5.

## Validazione G5 (ADR-017)

Per promozione meta-synthesis:
- DSR ≥ 0.95 (molti test multipli, threshold molto alto)
- PBO < 0.5 (overfitting risk alto su ensemble)
- CPCV OOS Sharpe > 0.5
- 250+ paper sessions con pass-rate ≥ 90%

Meta-synthesis è il più complesso da validare (multiple lanes → multiple parameters → high overfitting risk). **Hanno meta-labeling + Purged K-Fold è essenziali**.
