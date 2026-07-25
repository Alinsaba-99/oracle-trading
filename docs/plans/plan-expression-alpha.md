# Piano: Expression-based Alpha + Intraday Crypto + Multi-Asset

> Supera i limiti delle features tecniche statiche su daily.
> 3 direttrici parallele che convergono in un unico GA pipeline.

---

## Architettura target

```
┌─────────────────────────────────────────────────────────────────────┐
│                     GA PIPELINE (esistente)                          │
│  NSGA-II · 4-island · WalkForward · 4-objective                     │
│  signal_factory → BacktestSignal Protocol → VectorizedEngine         │
└─────────────────────────────────────────────────────────────────────┘
         ▲                     ▲                     ▲
         │                     │                     │
┌────────┴────────┐  ┌────────┴────────┐  ┌────────┴────────┐
│ ExpressionAlpha │  │  IntradaySignal  │  │  PairTradingSig │
│    (A)          │  │     (B)         │  │     (C)         │
│ GP-evolved      │  │ KNN/Alpha su    │  │ Cointegration   │
│ operator trees  │  │ 1h BTC/ETH      │  │ spread trading  │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         ▲                     ▲                     ▲
         │                     │                     │
┌────────┴────────┐  ┌────────┴────────┐  ┌────────┴────────┐
│ Operator Lib    │  │ CCXT Importer   │  │ Cointegration   │
│ 25+ operators   │  │ Intraday store  │  │ Engine          │
│ (ts_mean, rank, │  │ (Parquet)       │  │ (statsmodels)   │
│  correlation..) │  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## Phase A: Expression-based Alpha Engine

### A1 — Operator Library (1 sessione)

Definire operatori come funzioni Polars/NumPy pure:

| Categoria | Operatori |
|-----------|-----------|
| **Time-series** | `ts_mean(x, d)`, `ts_std(x, d)`, `ts_sum(x, d)`, `ts_prod(x, d)`, `ts_min(x, d)`, `ts_max(x, d)`, `ts_argmax(x, d)`, `ts_argmin(x, d)` |
| **Cross-sectional** (future) | `rank(x)`, `scale(x)`, `zscore(x)` |
| **Math** | `abs(x)`, `sign(x)`, `log(x)`, `sqrt(x)`, `-x`, `x + y`, `x - y`, `x * y`, `x / y` |
| **Finance** | `correlation(x, y, d)`, `covariance(x, y, d)`, `delta(x, d)`, `sma(x, d)`, `ema(x, d)` |

**File:** `genetics/alpha/operators.py` — ~150 righe, test incluso.

### A2 — Expression AST + Parser (1 sessione)

Rappresentazione dell'espressione come tree:

```
ExpressionNode:
  op: str          # nome operatore
  args: list[ExpressionNode | str]  # sotto-espressioni o nomi foglia
```

Parser da stringa → AST:
```
"sma(close, 20) / ts_std(close, 20)"
  → Div(Sma(Leaf("close"), 20), TsStd(Leaf("close"), 20))
```

**File:** `genetics/alpha/expression.py` — ~200 righe, test incluso.

### A3 — GP Genome Encoding (1 sessione)

Usare DEAP `gp` module:
- Primitive set con tutti gli operatori
- Terminal set: close, open, high, low, volume, returns, vwap
- Tree depth constraints (max 4-5 livelli)
- Crossover: subtree swapping
- Mutation: subtree random generation / point mutation

**Vincoli:**
- Max depth = 5 (evita overfitting)
- Max operators = 5 per individuo (efficienza computazionale)
- Penalty per alberi troppo profondi

**File:** `genetics/genome/expression_codec.py` — ~200 righe.

### A4 — ExpressionToSignal + GA Integration (1 sessione)

- `ExpressionGenomeToSignal(Genome)`: prende l'albero GP e lo computa sui dati
- `GenomeConfig.expressions: bool = False`
- `GAConfig.signal_type = "expression"`
- Integrazione con evaluator esistente

**File:** `genetics/genome/expression_signal.py` — ~150 righe.

### A5 — GA Run + Validazione (1 sessione)

- Run su SPY daily (pop=20, gen=30, 3-fold WFA)
- Confronto: expression-alpha vs KNN vs hybrid
- Metriche OOS concatenated
- Analisi fattori scoperti

---

## Phase B: Intraday Crypto Pipeline

### B1 — Data Importer (1 sessione)

Scaricare 1h OHLCV per BTC e ETH via yfinance:

```python
btc = yf.download("BTC-USD", period="5y", interval="1h")
# → ~43k barre
```

Salvare in `data/intraday/btc_1h.parquet`.

**File:** `experiments/scripts/fetch_intraday.py` — ~50 righe.

### B2 — Feature Computation su 50k barre (1 sessione)

Verificare che le feature attuali (RSI, CCI, ADX, WT, MOM) scalino a 50k barre:
- KNN con lookback=200 (vs 100 su daily)
- Expanding z-score su 50k = 1.25B operazioni — OK (NumPy vettorizzato)
- Tempo: ~2-3s per evaluation

### B3 — GA Run Intraday (1 sessione)

- KNN + Hybrid su BTC 1h
- pop=12, gen=15, 3-fold WFA (ogni fold = ~14k barre)
- Confronto metriche OOS con daily

---

## Phase C: Multi-Asset Pair Trading

### C1 — Cointegration Engine (1 sessione)

Usare `statsmodels.tsa.stattools.coint` per test di cointegrazione:

```python
from statsmodels.tsa.stattools import coint
score, pvalue, _ = coint(asset_a, asset_b)
# pvalue < 0.05 → cointegrati
```

**File:** `analytics/technical/pair_trading.py` — ~100 righe.

### C2 — Pair Trading Signal (1 sessione)

Segnale: quando lo spread (ratio dei prezzi) devia di N std dalla media rolling,
trade il revert:

```
z_score = (spread - spread.rolling_mean(20)) / spread.rolling_std(20)
if z_score > 2: short spread
if z_score < -2: long spread
```

Parametri GA-ottimizzabili:
- rolling_window (10-60)
- entry_threshold (1.0-3.0)
- exit_threshold (0.0-1.0)

**File:** `genetics/genome/pair_signal.py` — ~150 righe.

### C3 — GA Run Pair Trading (1 sessione)

- Pairs: SPY/QQQ, BTC/ETH
- 3-fold WFA su spread
- Confronto metriche

---

## Timeline

```
Sessione 1:  A1 (Operator Library)  +  B1 (Data Importer)
Sessione 2:  A2 (Expression AST)    +  C1 (Cointegration)
Sessione 3:  A3 (GP Encoding)       +  B2 (Intraday Features)
Sessione 4:  A4 (GA Integration)    +  C2 (Pair Signal)
Sessione 5:  A5 + B3 + C3 (GA Runs + Analisi)
```

Ogni sessione: ~1-2 ore.

---

## Dipendenze

```
A1 → A2 → A3 → A4 → A5
B1 → B2 → B3
C1 → C2 → C3

A, B, C paralleli fino alla fase GA Run
Tutte e 3 convergono in Sessione 5 (confronto risultati)
```

---

## Metriche di successo

| KPI | Target | Misura |
|-----|--------|--------|
| Expression-alpha Sharpe OOS | > 0.5 | Walkforward causale post-fix |
| Intraday hybrid Sharpe OOS | > 0.8 | Crypto 1h con costi |
| Pair trading Sharpe OOS | > 0.5 | Spread BTC/ETH |
| Diversity Pareto front | ≥ 5 individui | NSGA-II a 4 obiettivi |
| Tempo per evaluation | < 5s | 50k barre intraday |
