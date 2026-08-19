# 13 Meta-synthesis — Capability Map per Oracle

> Cosa costruire in Oracle (combo 12 domains → 1 decision).

## ✅ Già in Oracle

| Capability | File | Note |
|---|---|---|
| Lane B backtester | `analytics/strategy/lane_b_backtester.py` | Sharpe 0.93 fundamental equity |
| Lane D VRP backtester | `analytics/strategy/lane_d_vrp_backtest.py` | Sharpe -0.08 (edge assente — fix con BL-KB-47 regime filter) |
| AI Analyst Swarm | `analytics/ai_analysts/swarm.py` | 5 analysts + Synthesizer + Skeptic + Risk Manager |
| PaperBroker + Orchestrator | `execution/brokers/paper.py` + `execution/paper_orchestrator.py` | Step 4 Opzione C MVP |
| NautilusTrader + vectorbt + polars + cvxpy | (installed) | Backtest engines |

## 🔨 P1 — Implementare prossimo (combo 12 domains → 1 decision)

### BL-KB-92: Meta-synthesis orchestrator
- **Perché**: Renaissance pattern. Combo 11 lanes + regime classifier + HRP allocator + meta-label sizer.
- **Cosa**: `analytics/strategy/meta_synthesis.py:MetaSynthesisOrchestrator` con:
  - Inputs: Lane A (SPY 1h price) + Lane B (composite fundamental) + Lane D (VRP fixed) + Lane F (crypto L2) + Lane G (COT positioning) + Lane H (intermarket rotation) + Lane I (seasonal) + Lane J (crypto on-chain) + Lane K (behavioral Taleb barbell)
  - Regime classifier (BL-KB-93 Hamilton HMM)
  - HRP allocator (BL-KB-94)
  - Meta-label sizer (BL-KB-95)
  - DSR/PBO/CPCV validation (BL-KB-96)
- **Output**: final allocation per asset class + position sizes.
- **Tempo**: ~7-10 giorni (depends on BL-KB-93..96).
- **Costo**: $0.

### BL-KB-93: Hamilton HMM regime classifier
- **Perché**: Hamilton 1989 regime switching. Regime-aware allocation.
- **Cosa**: `analytics/strategy/meta/regime_classifier.py:HamiltonRegimeClassifier` con:
  - `pip install hmmlearn`
  - Train HMM on macro features (GDP growth, inflation, yield curve, VIX)
  - 4 regimes: bull, bear, recession, expansion
  - Output: filtered probability of each state per date
- **Tempo**: ~3-5 giorni.
- **Costo**: $0.

### BL-KB-94: HRP portfolio allocator
- **Perché**: Lopez de Prado 2016. Robust OOS, no matrix inversion.
- **Cosa**: `analytics/strategy/meta/hrp_allocator.py:HRPAllocator` con:
  - `pip install PyPortfolioOpt`
  - Hierarchical clustering on lane return correlations
  - Recursive bisection allocation
  - Output: weight per lane per date
- **Tempo**: ~2-3 giorni.
- **Costo**: $0.

### BL-KB-95: Meta-labeling position sizer
- **Perché**: Lopez de Prado 2018. Separates side (direction) from size (precision).
- **Cosa**: `analytics/strategy/meta/meta_labeler.py:MetaLabeler` con:
  - Secondary ML model (RandomForest or GradientBoosting)
  - Inputs: primary signal (long/short) + features (regime, sentiment, etc.)
  - Output: position size [0, 1] continuous or {0, 1} binary
  - Train with Purged K-Fold CV (BL-KB-19 dominio 03)
- **Tempo**: ~5-7 giorni.
- **Costo**: $0.

### BL-KB-96: Ensemble validation pipeline
- **Perché**: ADR-017 G5 gate. DSR + PBO + CPCV + factor filter per ensemble.
- **Cosa**: `analytics/validation/ensemble_pipeline.py:EnsembleValidationPipeline` con:
  - Run DSR + PBO + CPCV (BL-KB-19..21 dominio 03)
  - Factor filter (BL-KB-22 dominio 03) for new signals
  - Output: ValidationReport per ensemble + each lane
  - Trigger deployment gate (paper → shadow → evaluation → funded)
- **Tempo**: ~5-7 giorni.

## 🔨 P2 — Implementare per live trading

### BL-KB-97: Live meta-synthesis orchestrator
- **Perché**: post-validation, live signal → paper broker.
- **Cosa**: estendere `execution/paper_orchestrator.py:PaperOrchestrator` con:
  - Signal sources: Lane A+B+C+D+E+F+G+H+I+J+K outputs
  - Run meta-synthesis (BL-KB-92) per signal cycle
  - Output: OrderIntent list
  - Connect to PaperBroker for execution
- **Tempo**: ~5-7 giorni (depends on BL-KB-92).

### BL-KB-98: Ensemble backtest harness
- **Perché**: backtest all lanes together + measure ensemble metrics.
- **Cosa**: `analytics/strategy/meta/ensemble_backtest.py:EnsembleBacktestHarness` con:
  - Run all lanes over historical data
  - HRP allocation per date
  - Track ensemble equity curve + Sharpe + Max DD
  - Compare ensemble vs single-lane performance
- **Tempo**: ~5-7 giorni.

## 🔄 P3 — Deferrire

- **Live HFT execution** — requires paid infrastructure (colocation + direct market access).
- **Alternative data integration** (satellite + credit card + web scraping) — paywalled.
- **Numerai tournament-style meta-synthesis** — defer to P3.

## ❌ Hard-blocked (paywalled)

- Bloomberg B-Pipe + terminal — $24k/yr
- Refinitiv Eikon — $1.8k/mo
- AQR Premium factor library — institutional
- WorldQuant Alpha — institutional
- Two Sigma Vint — institutional
- Numerai historical — limited free
- QuantConnect Premium — $20-100/mo

## Sequenza implementazione raccomandata

```
BL-KB-93 Hamilton HMM regime         (~3-5g)
BL-KB-94 HRP portfolio allocator     (~2-3g)
BL-KB-95 Meta-labeling position sizer (~5-7g)
BL-KB-96 Ensemble validation pipeline (~5-7g)
BL-KB-92 Meta-synthesis orchestrator  (~7-10g)
BL-KB-97 Live orchestrator            (~5-7g)
BL-KB-98 Ensemble backtest harness    (~5-7g)
```

Totale: **~32-46 giorni** per meta-synthesis P1+P2.

## Prossimo step

Dopo P1+P2:
1. Run ensemble backtest on 2010-2025 with all lanes
2. DSR/PBO/CPCV validation
3. **Target**: ensemble Sharpe > 1.0 (vs single-lane 0.5-0.9), max DD < 25%
4. Promozione paper trading → shadow → evaluation → funded

## Riepilogo Knowledge Base 13 domini completato

| # | Dominio | Status | Backlog items | Tempo stimato |
|---|---|---|---|---|
| 01 | Fundamental | ✅ DONE | BL-KB-01..08 (8) | ~15-22g |
| 02 | Macro | ✅ DONE | BL-KB-09..18 (10) | ~23-33g |
| 03 | Quant / DSR / PBO | ✅ DONE | BL-KB-19..27 (9) | ~19-31g |
| 04 | Order flow / L2 | ✅ DONE | BL-KB-28..37 (10) | ~22-33g |
| 05 | Sentiment | ✅ DONE | BL-KB-38..47 (10) | ~19-31g |
| 06 | Positioning / COT | ✅ DONE | BL-KB-48..54 (7) | ~11-16g |
| 07 | News automated | ✅ DONE | BL-KB-55..60 (6) | ~16-28g |
| 08 | Intermarket | ✅ DONE | BL-KB-61..68 (8) | ~19-29g |
| 09 | Cyclical | ✅ DONE | BL-KB-69..71 (3) | ~7-11g |
| 10 | Seasonal | ✅ DONE | BL-KB-74..78 (5) | ~7-10g |
| 11 | On-chain | ✅ DONE | BL-KB-79..85 (7) | ~22-33g |
| 12 | Behavioral | ✅ DONE | BL-KB-86..91 (6) | ~16-25g |
| 13 | Meta-synthesis | ✅ DONE | BL-KB-92..98 (7) | ~32-46g |
| **TOTAL** | **13 domains** | ✅ ALL DONE | **98 backlog items** | **~208-348 giorni** |

**Target Oracle**: 11-lane ensemble (Lane A+B+C+D+E+F+G+H+I+J+K) con HRP allocator + Hamilton HMM regime + meta-labeling sizer + DSR/PBO/CPCV validation. **Aspirational Sharpe 1.0-1.5** (vs Medallion > 9). $0 data + OSS tools. 5y backtest target.
