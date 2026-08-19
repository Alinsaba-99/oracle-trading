# Dominio 03 — Quant / DSR / PBO / CPCV

> Knowledge base Oracle — studio approfondito 2026-08-17 via Tavily API.
> Obiettivo: mappare letteratura su backtest overfitting, multiple testing, deflated Sharpe, PBO, CPCV.

## Sintesi esecutiva

Il **dominio quant methodology** è la metaregola che validazione ADR-017 (Backtest overfitting validation upgrade). Tutti gli edge documentati nei domini 01 (fundamental) + 02 (macro) devono superare DSR/PBO/CPCV prima di promozione paper → shadow → evaluation → funded.

Tre livelli di validazione:

1. **PSR (Probabilistic Sharpe Ratio)** — Bailey-Lopez de Prado 2012. Corregge Sharpe per non-normalità (skew + kurtosis). Confidence interval su Sharpe observed. MinTRL (minimum track record length) per skill evidence.
2. **DSR (Deflated Sharpe Ratio)** — Bailey-Lopez de Prado 2014. Estende PSR correggendo per **multiple testing** (N strategy variants tested). `DSR = Phi((SR - SR0) / SE(SR))` dove SR0 = expected max Sharpe under null.
3. **PBO (Probability of Backtest Overfitting)** — Bailey et al. 2017. CSCV (Combinatorially Symmetric Cross-Validation). Stima la probabilità che l'IS champion rank sotto mediana OOS. **PBO < 0.5 = non overfit**.
4. **CPCV (Combinatorial Purged Cross-Validation)** — Lopez de Prado 2018. Estende PBO con **purging + embargo** per evitare leakage. Genera multipli backtest paths.

**Threshold Oracle ADR-017**:
- DSR ≥ 0.95
- PBO < 0.5 (idealmente < 0.1)
- CPCV OOS Sharpe > 0.5
- 250+ paper sessions con pass-rate ≥ 90%

**Factor zoo + replication crisis**:
- Harvey-Liu-Zhu (2016): 316+ fattori pubblicati dal 1963. t-stat threshold >3.0 (non >2.0).
- Hou-Xue-Zhang (2020): 452 anomalie testate, ~65% non replicano OOS o perdono >50% alpha.
- McLean-Pontiff (2016): post-publication decay ~58% su long-short anomaly returns. Arbitraggio erode.

**Stack Oracle**:
- ✅ NautilusTrader + vectorbt + polars + cvxpy installati (vedi `live-readiness-assessment`)
- ❌ purgedcv (MIT OSS) NON installato — TODO BL-KB-19

## Cap to build

1. **purgedcv integration** — `pip install purgedcv` (MIT OSS, https://github.com/eslazarev/purged-cross-validation). Implementa Purged K-Fold, embargo, CPCV, DSR, PSR. TODO BL-KB-19
2. **DSR calculator** — funzione `deflated_sharpe_ratio(returns, n_trials, sr_benchmark=0.0)`. TODO BL-KB-20
3. **PBO calculator** — funzione `pbo(returns_matrix)` con CSCV. TODO BL-KB-21
4. **Factor zoo filter** — applicare Harvey-Liu-Zhu threshold t-stat >3.0 a nuovi signal discoveries. TODO BL-KB-22
5. **Triple barrier labeling** (Lopez de Prado 2018) — per ML strategies. TODO BL-KB-23
6. **Fractional differencing** — features stationary con memory preservation. TODO BL-KB-24
7. **Meta-labeling** — secondary ML model per position sizing. TODO BL-KB-25

Vedi [literature.md](literature.md), [data-audit.md](data-audit.md), [edge.md](edge.md), [capability-map.md](capability-map.md).
