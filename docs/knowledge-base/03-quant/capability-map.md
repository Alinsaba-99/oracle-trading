# 03 Quant — Capability Map per Oracle

> Cosa costruire prima in Oracle (methodology layer essenziale per ADR-017 G5).

## ✅ Già in Oracle

| Capability | File | Note |
|---|---|---|
| NautilusTrader | (installed, no integration code yet) | Event-driven backtesting engine |
| vectorbt | (installed, no integration code yet) | Vectorized backtesting engine |
| polars | (installed) | DataFrame ops |
| cvxpy | (installed) | Convex optimization |
| FRED VIX loader | `analytics/macro/fred.py:FREDClient` | Macro data fetch |
| Lane B backtester | `analytics/strategy/lane_b_backtester.py` | CompositeLaneBScore Sharpe 0.93 |
| Lane D VRP backtester | `analytics/strategy/lane_d_vrp_backtest.py` | Sharpe -0.08 (no edge) |

## 🔨 P1 — Implementare prossimo (critical per ADR-017 G5)

### BL-KB-19: purgedcv integration
- **Perché**: ADR-017 requires DSR ≥ 0.95 + PBO < 0.5 + CPCV OOS Sharpe > 0.5. purgedcv ha tutto.
- **Cosa**: `uv add purgedcv`. Wrappers in `analytics/validation/` per integrare con Lane backtesters.
- **Output**: `PurgedKFoldCV`, `CPCVBacktest`, `deflated_sharpe_ratio`, `probabilistic_sharpe_ratio`, `pbo`.
- **Tempo**: ~1 giorno.
- **Costo**: $0.

### BL-KB-20: DSR + PSR calculator
- **Perché**: ogni Lane backtest deve passare DSR ≥ 0.95 per promozione paper trading.
- **Cosa**: `analytics/validation/dsr.py:DSRCalculator` con:
  - `compute_dsr(returns: np.ndarray, n_trials: int, sr_benchmark: float = 0.0) -> float`
  - `compute_psr(returns: np.ndarray, sr_benchmark: float = 0.0) -> float`
  - `min_trl(returns, target_sharpe, confidence=0.95) -> int`
- **Output**: DSR/PSR values per Lane A/B/C/D.
- **Tempo**: ~1-2 giorni.
- **Costo**: $0.

### BL-KB-21: PBO + CSCV calculator
- **Perché**: ADR-017 requires PBO < 0.5.
- **Cosa**: `analytics/validation/pbo.py:PBOCalculator` con:
  - `compute_pbo(returns_matrix: np.ndarray) -> float`
  - Returns matrix: shape (T, N) con N strategy variants.
  - Output: PBO probability + logit(ω) distribution + IS/OOS Sharpe scatter.
- **Tempo**: ~2-3 giorni.
- **Costo**: $0.

### BL-KB-22: Factor zoo filter
- **Perché**: Harvey-Liu-Zhu 2016 raccomanda t-stat >3.0. Hou-Xue-Zhang 2020: 65% non replicano.
- **Cosa**: `analytics/validation/factor_filter.py:FactorFilter` con:
  - `check_anomaly(returns, factor_returns, threshold=3.0) -> dict`
  - Bonferroni + Holm + BHY multiple testing correction
  - q5-factor regression (Mkt + ME + I/A + ROE + PEAD)
- **Tempo**: ~3-5 giorni.

### BL-KB-23: Triple Barrier Labeling + Meta-labeling
- **Perché**: ML pipeline per sizing decoupled da signal prediction.
- **Cosa**: `analytics/ml/triple_barrier.py` con:
  - `label_triple_barrier(prices, take_profit_pct, stop_loss_pct, time_limit_bars)`
  - `meta_label(primary_signal, returns, features)` → secondary ML model per position size
  - CUSUM filter pre-select events
- **Tempo**: ~3-5 giorni.

### BL-KB-24: Fractional Differencing
- **Perché**: features stationary con memory preservation per ML.
- **Cosa**: `analytics/features/fractional_diff.py:fractional_diff(series, d)` con:
  - Compute fractionally differenced series (d in (0, 1))
  - ADF test for stationarity
  - Find minimum d that passes
- **Tempo**: ~1-2 giorni.

### BL-KB-25: Kenneth French + AQR data adapters
- **Perché**: FF5F regression per alpha decomposition (vedi BL-KB-06 dominio 01).
- **Cosa**: `analytics/macro/ff_data.py:FFDataClient` con:
  - Fetch FF3/FF5/MOM/PEAD factor returns (monthly + daily)
  - Parse zip files from `mba.tuck.dartmouth.edu/pages/faculty/ken.french/`
  - Cache su `data/macro/fama_french/`
- **Cosa**: anche `analytics/macro/aqr.py:AQRDataClient` per QMJ/BAB factor returns.
- **Tempo**: ~2-3 giorni.

## 🔨 P2 — Implementare per validazione pipeline

### BL-KB-26: CPCV multi-path backtest
- **Perché**: ADR-017 requires CPCV OOS Sharpe > 0.5.
- **Cosa**: `analytics/validation/cpcv.py:CPCVBacktest` con:
  - Combinatorial purged cross-validation
  - Generate N choose k backtest paths
  - Aggregate OOS Sharpe distribution
- **Tempo**: ~3-5 giorni (depends on purgedcv integration BL-KB-19).

### BL-KB-27: Validation pipeline orchestrator
- **Perché**: ogni Lane backtest deve passare il validation layer automaticamente.
- **Cosa**: `analytics/validation/pipeline.py:ValidationPipeline` con:
  - Run DSR + PBO + CPCV + factor_filter su ogni strategy backtest
  - Output: `ValidationReport` con pass/fail per ogni gate
  - Trigger deployment gate (paper → shadow → evaluation)
- **Tempo**: ~3-5 giorni.

## 🔄 P3 — Deferrire

- **NautilusTrader integration** con Lane backtesters (already installed, but no wrappers per Lane A/B/C/D). Quando validation pipeline è ready, integrare.
- **vectorbt integration** per parameter sweeps su strategy families.
- **ML models** (gradient boosting, neural nets) per meta-labeling — quando BL-KB-23 triple barrier è ready.

## ❌ Hard-blocked (paywalled)

- **Bloomberg Backtester** — $24k/yr. Alternativa: vectorbt + NautilusTrader.
- **QuantConnect Premium** — $20-100/mo. Alternativa: local stack + purgedcv.

## Sequenza implementazione raccomandata

```
BL-KB-19 purgedcv integration     (~1g)   ← unlock DSR/PBO/CPCV
BL-KB-20 DSR + PSR calculator     (~1-2g) ← ADR-017 gate
BL-KB-21 PBO + CSCV calculator    (~2-3g) ← ADR-017 gate
BL-KB-25 Kenneth French adapter   (~2-3g) ← factor regression
BL-KB-22 Factor zoo filter        (~3-5g) ← Harvey-Liu-Zhu
BL-KB-23 Triple Barrier + Meta    (~3-5g) ← ML pipeline
BL-KB-24 Fractional Differencing  (~1-2g) ← feature engineering
BL-KB-26 CPCV multi-path          (~3-5g) ← ADR-017 gate
BL-KB-27 Validation pipeline      (~3-5g) ← orchestrator
```

Totale: **~19-31 giorni** per completare P1+P2 quant validation layer.

## Prossimo step

Dopo P1+P2 quant:
1. Ri-run Lane B backtest 2020-2025 → applica DSR/PBO/CPCV → vedi se passa ADR-017 G5.
2. Se passa → promuovi a paper trading live (Step 4 Opzione C followup).
3. Se non passa → indica overfitting → reject o re-tune.

**Target**: Lane B Composite (Sharpe 0.93 storico) → DSR > 0.95 + PBO < 0.1 + CPCV OOS Sharpe > 0.5 → ready per paper trading.
