# 03 Quant — Edge Plausibility

> Valutazione critica per ogni methodology quant. Dominio è **methodology layer** non signal layer.

## Edge summary

| Method | Edge | Author | Applicability |
|---|---|---|---|
| PSR (Probabilistic Sharpe Ratio) | confidence interval su Sharpe observed | Bailey-Lopez de Prado 2012 | Ogni backtest. N=1 special case di DSR |
| DSR (Deflated Sharpe Ratio) | multiple testing correction | Bailey-Lopez de Prado 2014 | Ogni backtest con N variants tested |
| PBO (Probability of Backtest Overfitting) | overfitting detection via CSCV | Bailey et al. 2017 | Multi-strategy grid backtest |
| CPCV (Combinatorial Purged CV) | realistic OOS multi-path | Lopez de Prado 2018 | ML pipeline + strategy validation |
| Triple Barrier Labeling | path-dependent ML labels | Lopez de Prado 2018 | ML training (non-fixed-horizon) |
| Meta-labeling | decoupled sizing model | Lopez de Prado 2018 | Secondary ML per position size |
| Fractional Differencing | stationary + memory features | Lopez de Prado 2018 | Feature engineering per ML |
| Factor zoo filtering | t-stat >3.0 threshold | Harvey-Liu-Zhu 2016 | Anomaly validation |
| Replicating anomalies | 65% non replicano | Hou-Xue-Zhang 2020 | Skepticism su nuovi fattori |
| Post-publication decay | -58% OOS | McLean-Pontiff 2016 | Aspettati ~half backtest alpha |

## Verdetto edge

**Edge non è un trading signal ma un methodology layer**:
1. **DSR/PBO/CPCV sono gates**: se un signal backtest passa DSR ≥ 0.95 + PBO < 0.1 + CPCV OOS Sharpe > 0.5 → promuovi a paper trading. Se no → reject.
2. **Factor zoo filter**: nuovi signals devono avere t-stat >3.0 (non >2.0) per superare multiple testing correction.
3. **Post-publication decay**: aspettati ~50% del backtest alpha storico (McLean-Pontiff + replicating anomalies).

## Cost-realism check

- **Costo implementazione**: ~$0 (tutto free OSS).
- **Tempo implementazione**: 5-10 giorni per purgedcv integration + DSR/PBO/CPCV calculators.
- **Ritorno**: ogni futuro signal può essere validato invece di solo backtested.

## Validazione G5 (ADR-017)

Per ogni strategy promotion paper → shadow → evaluation → funded:
- **DSR ≥ 0.95**: multiple testing correction con N variants tested
- **PBO < 0.5**: probability that IS champion ranks below OOS median
- **CPCV OOS Sharpe > 0.5**: multi-path OOS validation
- **250+ paper sessions con pass-rate ≥ 90%**: track record statistics
- **PSR ≥ 0.95** (single-strategy): confidence su Sharpe observed
- **MinTRL**: minimum track record length per skill evidence

Stack Oracle da buildare:
1. `purgedcv` integration (pip install)
2. `analytics/validation/dsr.py` — DSR + PSR calculator
3. `analytics/validation/pbo.py` — PBO via CSCV
4. `analytics/validation/cpcv.py` — multi-path backtest
5. `analytics/validation/factor_filter.py` — t-stat >3.0 threshold

Dopo, ogni Lane A/B/C/D backtest deve passare il validation layer prima di deployment.
