# 13 Meta-synthesis — Literature Review

> Fonti: Tavily API (advanced) 2026-08-17. URL verified.

## 1. Renaissance Medallion pattern

### Jim Simons + Medallion Fund 1988-2018

- **Annual return**: +66.1% gross, +39% net (post 5% mgmt + 44% perf).
- **Sharpe**: > 9 (3-4x AQR + Citadel).
- **Hit rate**: 50.75% across millions of trades.
- **Edge magnitude**: small statistical advantage × millions of bets.
- **Strategy**: multi-strategy ensemble, automated, no human bias.
- **Universe**: 5,000+ signals, all asset classes (equity, futures, FX, options).
- **Closed to outside investors** since 1993 (only Renaissance employees).

### Simons methodology

- Mathematician approach: pattern recognition in clean historical data.
- Model = data-driven, NOT market-theory-driven.
- "Stick to your model" even in volatile markets (avoid behavioral bias).
- Clean data > clever model (garbage-in, garbage-out).

### Edge drivers

- **Many small bets**: 100M+ trades/year. Law of large numbers → small advantages compound.
- **Diversification across signals**: low correlation among 5,000+ signals.
- **Speed**: HFT + microstructure edge (latency arbitrage pre-2010).
- **Data**: proprietary cleaned tick data + alternative data.

## 2. Meta-labeling (Lopez de Prado 2018)

### Side vs Size separation

- **Primary model**: predict direction (long/short). Optimize recall (high TP rate).
- **Meta-model**: predict position size (0 to 1). Optimize precision (filter false positives).
- **Decoupled problems**: classification (direction) + regression (size).

### Purged K-Fold CV

- Time-series CV con purging (avoid label overlap between train + test).
- Embargo (gap after test to handle serial correlation).
- Avoid data leakage standard K-Fold has on time series.

### Clustered Feature Importance

- Multicollinearity: features correlated → importance attribution ambiguous.
- Cluster features via hierarchical clustering → score clusters, not individual features.

## 3. Hamilton regime switching (1989)

### Hidden Markov Model (HMM)

- **States**: hidden (e.g., bull/bear/recession/expansion).
- **Transitions**: Markov chain, probability of switching states.
- **Observations**: returns, volatility, macro variables.
- **Output**: filtered probability of being in each state.

### Application to asset allocation

- Different strategies work in different regimes:
  - Bull regime: trend-following, momentum (Lane B value + Lane C momentum)
  - Bear regime: mean-reversion, defensive (Lane K behavioral + Taleb barbell)
  - Recession: flight to quality, low equity (Lane H intermarket + macro overlay)
  - Expansion: cyclical, sector rotation (Stovall model dominio 08)

### Hamilton 1989

**Paper**: Hamilton, J. (1989). *A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle*. Econometrica.

- Original application: business cycle dating.
- Extended to asset allocation: Ang-Bekaert 2002, 2004.

## 4. Hierarchical Risk Parity (HRP)

### Lopez de Prado 2016

**Paper**: Lopez de Prado, M. (2016). *Building Diversified Portfolios that Outperform Out-of-Sample*. Journal of Portfolio Management.

- **Problem with Markowitz**: matrix inversion unstable when correlation matrix ill-conditioned.
- **HRP solution**: hierarchical clustering of assets → allocate risk recursively based on tree structure.
- **Advantages**:
  - No matrix inversion → numerically stable.
  - No expected return estimates → robust OOS.
  - Mimics structure of correlation tree.
- **Outperformance**: HRP beats Markowitz OOS.

### Implementation (Python `riskparity.py` or `PyPortfolioOpt`)

- Step 1: hierarchical clustering of asset correlations (scipy `linkage` function).
- Step 2: recursive bisection — split tree into sub-clusters, allocate risk equal across sub-clusters.
- Step 3: leaf-level weight = recursive allocation.

## 5. Signal weighting methods

### Equal weight

- All signals weight 1/N. Simple baseline.
- Suffers if one signal dominates overfitting.

### Inverse volatility

- weight = 1 / σ_signal. Lower-vol signals get higher weight.
- Risk parity approach applied to signal level (not asset level).

### Signal weighting (return correlation)

- weight = correlation(signal, future returns) / Σ.
- Signal with higher predictive power gets higher weight.

### HRP (correlation-based)

- Cluster signals via correlation.
- Allocate risk across clusters.
- Robust to multicollinearity.

### Meta-labeling (Lopez de Prado)

- Secondary ML model takes primary signal outputs → predicts position size.
- Trained with Purged K-Fold CV.
- Outputs size 0 to 1 (continuous) or 0/1 (binary).

## 6. Ensemble methods

### Voting

- Each strategy votes long/short/flat.
- Majority wins.
- Simple, robust.

### Stacking

- Secondary ML model combines primary outputs (one per strategy).
- Trained on historical strategy returns.
- Better than voting if strategies correlated.

### Bayesian Model Averaging

- Posterior probability weighting of strategies.
- Update weights as new data arrives.
- Robust to overfitting single strategy.

### Random Forest Feature Importance

- Treat each strategy as feature.
- Random forest outputs feature importance → weight per strategy.
- Handles nonlinear interactions.

## 7. Cap summary

**Edge reale Renaissance pattern**:
- 5,000+ small signals combined → Sharpe > 9.
- Inverse volatility weighting + meta-labeling sizing.
- Clean data > clever model.
- No human bias (automated).

**Edge applicabile Oracle**:
- Combina Lane A+B+C+D+E+F+G+H+I+J+K (11 lanes from 12 domains).
- HRP for portfolio allocation across lanes.
- Hamilton HMM for regime switching.
- Meta-labeling for sizing.

**Edge hard-blocked**:
- Real Renaissance data + infrastructure → enterprise, replicating impossible.
- High-frequency latency arbitrage → no free tick data + no HFT infrastructure.

**Implication**: Oracle non può replicare Medallion. Ma può:
- Costruire 11-lane ensemble con HRP + regime switching + meta-labeling.
- Aspettarsi Sharpe 1.0-1.5 (vs Medallion > 9), non superare.
- $0 data + OSS tools → still profitable su 5y horizon.
