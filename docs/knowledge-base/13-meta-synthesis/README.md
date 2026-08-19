# Dominio 13 — Meta-synthesis / Renaissance pattern

> Knowledge base Oracle — studio approfondito 2026-08-17 via Tavily API.
> **Dominio culmine** — combo dei 12 precedenti in un'unica decisione.

## Sintesi esecutiva

La meta-synthesis è il **crux dell'intero progetto Oracle**: come combinare 12 domini di analisi eterogenei (fundamental + macro + quant + order flow + sentiment + positioning + news + intermarket + cyclical + seasonal + on-chain + behavioral) in un'unica decisione di trading.

1. **Renaissance Medallion** (Jim Simons 1988-2018): +66.1%/yr annuo (39% net), Sharpe > 9, 50.75% hit-rate. Multi-strategy ensemble di migliaia di small signals, automated, no human bias. ~5,000+ signals totali, weight = inverse volatility, position size = meta-labeling.

2. **Lopez de Prado meta-strategy** (2018): meta-labeling separates primary signal prediction (high recall) from sizing (high precision). Purged K-Fold CV per OOS validation. Clustered feature importance per multicollinearity.

3. **Hamilton regime switching** (1989): hidden Markov models per state identification. Portfolio adapts to regime (bull, bear, recession, expansion).

4. **Hierarchical Risk Parity** (Lopez de Prado 2016): non-parametric portfolio allocation via hierarchical clustering. No matrix inversion, no expected return estimates. Robust OOS.

5. **Signal weighting methods**:
   - Equal weight (baseline)
   - Inverse volatility (lower-vol signals get higher weight)
   - Signal weighting (correlation with future returns)
   - HRP (correlation-based hierarchical clusters)
   - Meta-labeling (secondary ML for sizing)

6. **Ensemble methods**:
   - Voting (majority)
   - Stacking (secondary ML combines primary outputs)
   - Bayesian model averaging
   - Random forest feature importance

**Cap to build Oracle**:
1. Signal weighting system (5 methods: equal + inverse vol + signal + HRP + meta-label)
2. Regime classifier (Hamilton HMM o macro regime classifier dominio 02)
3. Multi-lane orchestrator (Lane A+B+C+D+E+F+G+H+I+J+K ensemble)
4. Meta-synthesis layer (combina lane signals + regime → final allocation)
5. DSR/PBO/CPCV validation pipeline (dominio 03)

Vedi [literature.md](literature.md), [data-audit.md](data-audit.md), [edge.md](edge.md), [capability-map.md](capability-map.md).
