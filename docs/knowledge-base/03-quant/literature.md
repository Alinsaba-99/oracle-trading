# 03 Quant — Literature Review

> Fonti: Tavily API (advanced, AI-optimized) 2026-08-17. URL verified per paper.

## 1. Sharpe ratio corrections

### Probabilistic Sharpe Ratio (PSR) — Bailey-Lopez de Prado 2012

**Paper**: Bailey, D., Lopez de Prado, M. (2012). *The Sharpe Ratio Efficient Frontier*. Journal of Risk, 15(2), 3-44.

- **PSR formula**: `PSR(SR) = Z((SR - SR_benchmark) * sqrt(T-1) / sqrt(1 - γ3*SR + (γ4-1)/4 * SR²))`
  - γ3 = skewness, γ4 = kurtosis
  - T = number of return observations
  - SR_benchmark = reference Sharpe (typically 0)
- **MinTRL** = minimum track record length to evidence skill at confidence level.
- **Edge**: PSR > 0.95 = alta probabilità che Sharpe osservato > 0 vero.
- **Limitation**: non corregge per multiple testing.

### Deflated Sharpe Ratio (DSR) — Bailey-Lopez de Prado 2014

**Paper**: Bailey, D., Lopez de Prado, M. (2014). *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality*. Journal of Portfolio Management, 40(5), 94-107.

- **DSR formula**: `DSR = Phi((SR - SR0) / SE(SR))` dove:
  - SR0 = `sqrt(2 * ln(N)) * SE(SR)` (expected max Sharpe under null, assuming N iid trials)
  - SE(SR) = `sqrt((1 - γ3*SR + (γ4-1)/4 * SR²) / (T-1))`
  - N = number of independent strategy variants tested
- **Euler-Mascheroni constant** appears in SR0 formula for finite-sample correction.
- **Threshold Oracle**: DSR ≥ 0.95 (vedi ADR-017).
- **Special case**: N=1 → DSR = PSR.

## 2. Backtest overfitting

### Pseudo-Mathematics and Financial Charlatanism — Bailey-Borwein-Lopez de Prado-Zhu 2014

**Paper**: Bailey, D., Borwein, J., Lopez de Prado, M., Zhu, J. (2014). *Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance*. Notices of the AMS, 61(5), 458-471.

- **Proof**: high simulated performance achievable after testing relatively small number of strategy configurations.
- **CSCV** introduced as evaluation methodology.
- **Implication**: backtest con N parametri testati → aspettati max Sharpe elevato anche sotto null hypothesis.

### Probability of Backtest Overfitting (PBO) — Bailey et al. 2017

**Paper**: Bailey, D., Borwein, J., Lopez de Prado, M., Zhu, Q. (2017). *The Probability of Backtest Overfitting*. Journal of Computational Finance.

- **CSCV algorithm**:
  1. Split returns matrix (T × N strategies) into N_e even subsamples
  2. For each combinatorial split: in-sample (IS) = N/2 blocks, out-of-sample (OOS) = N/2 blocks
  3. For each split: rank strategies IS → find IS champion → check OOS rank of IS champion
  4. `ω = OOS rank / (N+1)`, logit(ω) = log(ω/(1-ω))
  5. PBO = fraction of splits where logit(ω) < 0 (IS champion below OOS median)
- **Number of splits**: C(N, N/2) — per N=16 → 12,870 splits.
- **Threshold**: PBO < 0.5 = non overfit. PBO < 0.1 = low overfit risk.

## 3. Cross-validation methods

### Combinatorial Purged Cross-Validation (CPCV) — Lopez de Prado 2018

**Book**: Lopez de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley.

- **Purging**: remove training observations within `t` bars after any test sample to avoid leakage from labels overlapping.
- **Embargo**: additional gap after test set to handle serial correlation.
- **Combinatorial**: generate N choose k backtest paths → multiple OOS evaluations.
- **vs Walk-Forward**: WF ha single path, sequence-biased, sample-inefficient. CPCV multi-path, less biased.
- **vs K-Fold**: K-Fold has leakage with time series. Purged K-Fold avoids leakage.

### Walk-Forward vs K-Fold vs CPCV comparison

- **Walk-Forward**: sequential, low sample efficiency, biased by data order.
- **K-Fold**: random split → leakage con time series (label overlap).
- **Purged K-Fold**: K-Fold con purging, no leakage.
- **CPCV**: combinatorial purged, multi-path, best for backtest overfitting detection.

## 4. Factor zoo + multiple testing

### Harvey-Liu-Zhu 2016

**Paper**: Harvey, C., Liu, Y., Zhu, H. (2016). *… and the Cross-Section of Expected Returns*. Review of Financial Studies.

- **316+ factors** published 1963-2014. Most fail multiple testing correction.
- **t-stat threshold raccomandato**:
  - Standard: 2.0 (95% confidence)
  - Bonferroni: 3.78 (più conservativo)
  - Holm: 3.78
  - BHY (Benjamini-Hochberg-Yekutieli): 3.18 (least conservative, recommended)
- **Threshold rising over time**: più fattori pubblicati → threshold più alto per nuovi.
- **Implication**: value/profitability/momentum classici sopravvivono (>3.0 t-stat), ma ~400 altri no.

### Hou-Xue-Zhang 2020

**Paper**: Hou, K., Xue, C., Zhang, L. (2020). *Replicating Anomalies*. Review of Financial Studies.

- **452 anomalies** testate con q-factor model.
- **~65% non replicano** o perdono >50% alpha OOS.
- **Robusti**: value (HML), profitability (ROE), investment (CMA/IVA), momentum (MOM).
- **Non replicano**: ~300 anomalies including many sentiment, technical, accrual-based.
- **q5 model** (Mkt + ME + I/A + ROE + PEAD) subsume molti.

### McLean-Pontiff 2016

**Paper**: McLean, R., Pontiff, J. (2016). *Does Academic Research Destroy Return Predictability?* Journal of Finance.

- **97 anomalies US stock** studiate pre vs post publication.
- **Post-publication decay**: -58% OOS anomaly returns (US). -36% post-sample, -58% post-publication.
- **Arbitrage erodes**: paper publication → hedge funds trade → alpha decays.
- **International less decay**: anomaly less known internationally.

## 5. AFML techniques (Lopez de Prado 2018)

### Triple Barrier Method

- **Label observations** by first barrier touched:
  - Upper horizontal: take-profit
  - Lower horizontal: stop-loss
  - Vertical: time limit
- **Path-dependent labeling** vs fixed-horizon. Better for ML training.
- **CUSUM filter** pre-selects events (structural breaks) per evitare whipsaws.

### Meta-labeling

- **Secondary ML model** che prende signal da primary model → outputs position size + direction.
- **Decouples prediction from sizing**: primary predicts direction, meta-label predicts size.
- **Improves Sharpe + reduce drawdown** documentato in HudsonThames research.

### Fractional Differencing

- **Problem**: integer differencing (d=1) removes memory. d=0 keeps non-stationary.
- **Solution**: fractional d in (0, 1) → stationary + retains memory.
- **ADF test** for stationarity, find minimum d that passes.
- **Use case**: features for ML that need stationarity + memory.

## 6. Backtesting framework comparison

### VectorBT (vectorized)

- **Pros**: fast (NumPy/Numba), large parameter sweeps, multi-asset.
- **Cons**: less realistic (no L2, partial fills, slippage models).
- **Use case**: research, parameter optimization.

### NautilusTrader (event-driven)

- **Pros**: realistic (order book, latency, fills), production-grade.
- **Cons**: slow, complex setup.
- **Use case**: live trading, final validation.

### Backtrader (legacy)

- **Pros**: easy, well-documented.
- **Cons**: no longer maintained, slower than vectorbt.
- **Use case**: deprecated.

### Stack Oracle 2026-08-17

- ✅ NautilusTrader installed
- ✅ vectorbt installed
- ✅ polars + cvxpy installed
- ✅ Nautilus + vectorbt for backtest + DSR/PBO/CPCV workflow

## 7. Cap summary

**Edge reale + methodology robusta**:
- DSR (multiple testing correction) — applicabile a ogni signal backtest
- PBO (CSCV) — overfitting detection
- CPCV (purging + embargo) — realistic OOS evaluation
- Triple Barrier + Meta-labeling — ML pipeline per sizing
- Fractional differencing — features stationary with memory

**Edge contestato / data mining**:
- ~400+ anomalies published → ~65% non replicano (Hou-Xue-Zhang)
- Post-publication decay -58% (McLean-Pontiff)
- t-stat >3.0 threshold necessario (Harvey-Liu-Zhu)

**Stack Oracle da buildare**:
- `purgedcv` install + integration
- DSR calculator
- PBO calculator
- Factor zoo filter per nuovi signals
