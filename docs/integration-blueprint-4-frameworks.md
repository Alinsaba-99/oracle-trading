# Framework Integration Blueprint — Zero Overlap, Pure Enhancement

> Data: 2026-07-28
> Scopo: Definire ESATTAMENTE cosa ogni framework aggiunge a Oracle,
> senza reimplementare nulla che Oracle già fa.

---

## Principio Guida

**Oracle NON ha bisogno di**:
- Un altro backtesting engine (ha NautilusTrader + vectorbt + PaperBroker)
- Un altro OMS/ledger (ha PostgreSQL + RecoveryService + Reconciliation)
- Un altro data pipeline (BL-301 con 7 sorgenti zero-cost)
- Un altro risk manager (ha PropFirmRiskGovernor + kernel deterministico)
- Un'altra strategia sandbox (genetics/gates già implementato)

**Oracle HA BISOGNO di**:
1. Factor zoo → da QLib (alpha definitions, non engine)
2. Overfitting defenses + time-series CV → da Inalpha (CPCV, PBO, DSR)
3. Portfolio construction → da PyPortfolioOpt (HRP)
4. Forecast scaling → da pysystemtrade (vol target, IDM, combination)

---

## 1. QLib (46.7K⭐, MIT) — Factor Zoo, NON Engine

### Cosa NON portare
| Modulo QLib | Perché NO |
|-------------|-----------|
| `qlib.backtest` | Oracle ha NautilusTrader + vectorbt |
| `qlib.data.dataset` | Oracle ha BL-301 Data Lake |
| `qlib.model` (LightGBM trainer) | ML già in `analytics/ml/` via LightGBM |
| `qlib.contrib.model.ensembler` | Oracle ha ensemble più specializzato |

### Cosa PORTARE

| Cosa | File QLib | File Oracle Target | Stima |
|------|-----------|-------------------|-------|
| **Alpha101 factor definitions** | `qlib.contrib.data.handler.py` Alpha101 | `analytics/strategy/catalog/alpha101.py` | 2gg |
| **Alpha158 factor definitions** | `qlib.contrib.data.loader.py` Alpha158DL | `analytics/strategy/catalog/alpha158.py` | 2gg |
| **RD-Agent pattern** | `qlib/contrib/rd_agent/` | `agents/rd_agent.py` | 5gg |

### Pattern d'integrazione (Adapter, non Copia)

```
QLib Alpha101/158/360 → QLibFactorAdapter(BaseSignal)
                         ↓
                   alpha101_0001() ... alpha101_0101()
                         ↓              come funzioni pure
                   signals_r3.py         che prendono OHLCV
                         ↓              e restituiscono segnale [-1,0,1]
                   SweepEngine testa su tutti gli asset
```

**Esempio concreto**: Alpha#001 `(close - open) / (high - low)` diventa:

```python
# analytics/strategy/catalog/alpha101.py
def alpha_001(data: pl.DataFrame) -> pl.Series:
    """Alpha#001: (close - open) / (high - low) — mean reversion"""
    o, h, l, c = [data[c] for c in ["open", "high", "low", "close"]]
    spread = h - l
    raw = (c - o) / spread.where(spread > 0, 1e-9)
    # Z-score threshold for mean reversion signal
    return (raw < -2.0).cast(pl.Int8)  # 1 when extreme
```

**Attenzione**: La maggior parte degli Alpha101 sono CROSS-SECTIONAL (classificano N titoli). Per futures (singolo contratto) servono adattamenti time-series. Solo ~30/101 alpha sono direttamente utilizzabili.

### Risultato netto
- **+100 nuove strategie** pronte per lo sweep
- **Zero overlap** con signals.py/signals_r1.py/signals_r2.py
- **Licenza MIT** → nessun problema legale

---

## 2. Inalpha (25⭐, AGPL-3.0) — Overfitting Defenses + CV

> **UPDATE 2026-08-15 (BL-508 / ADR-017)**: i moduli CPCV, PurgedKFold, PBO,
> DSR sono ora **implementati e cablati** in `analytics/qualification/dsr.py`
> come wrapper del MIT-licensed `purgedcv` (eslazarev/purged-cross-validation,
> v0.1.3 PyPI 1-ago-2026) + Apache-2.0 `mnemox-ai/deflated-sharpe`. **NON
> reimplementare da Inalpha** (AGPL-3.0, vincoli copyleft pesanti).
> `mlfinlab` (Hudson & Thames) è deprecato come aspirational reference:
> licenza "all rights reserved" (non più OSI), repo pubblico esiste solo come
> bug tracker, NON incorporabile senza licenza commerciale Business/Enterprise.
> Vedi ADR-017 per dettagli.

### Cosa NON portare
| Modulo Inalpha | Perché NO |
|----------------|-----------|
| `services/paper` (backtest engine) | Oracle ha NautilusTrader |
| `services/factor` (factor engine) | Oracle ha FactorTimingEngine già implementato |
| `services/research` (multi-agent debate) | Oracle ha `agents/analysts/` |
| `strategy_authoring` (LLM strategy) | Oracle ha `genetics/evolution.py` |
| `execution` (order routing) | Oracle ha OrderManager + risk kernel |
| `risk` engine | Oracle ha PropFirmRiskGovernor |

### Cosa PORTARE

> **UPDATE 2026-08-15 (BL-508)**: la tabella sottostante è **STORICA** e
> riflette il pre-BL-500 piano di reimplementazione da Inalpha. La realtà
> attuale: i 5 moduli sono già disponibili via `purgedcv` (MIT) +
> `mnemox-ai/deflated-sharpe` (Apache-2.0) → wrapper in
> `analytics/qualification/dsr.py`. NON serve reimplementare da Inalpha.

| Cosa | File Inalpha | File Oracle Target | Stato 2026-08-15 | Stima originale |
|------|-------------|-------------------|-------|-------|
| **Combinatorial Purged CV** | `cv.py` → `CombinatorialPurgedCV` | `analytics/qualification/dsr.py::combinatorial_purged_cv()` | ✅ DONE via `purgedcv` (BL-500) | 2gg |
| **PurgedKFold** | `cv.py` → `PurgedKFold` | `analytics/qualification/dsr.py::purged_k_fold()` | ✅ DONE via `purgedcv` (BL-500) | 1gg |
| **PBO (Prob. of Backtest Overfitting)** | `robustness.py` → `pbo()` | `analytics/qualification/dsr.py::probability_of_backtest_overfitting()` | ✅ DONE via `purgedcv` (BL-500) | 2gg |
| **Deflated Sharpe Ratio** | `robustness.py` → `deflated_sharpe()` | `analytics/qualification/dsr.py::deflated_sharpe_ratio()` | ✅ DONE via `purgedcv` + `mnemox-ai/deflated-sharpe` fallback (BL-500) | 1gg |
| **Bootstrap Sharpe CI** | `robustness.py` → `bootstrap_sharpe_ci()` | `analytics/metrics/bootstrap_sharpe.py` | ⏳ TODO (non bloccante; `purgedcv` non lo include, va implementato o preso da `arch` package) | 1gg |

### Pattern d'integrazione

```
Strategy candidate
     ↓
Backtest on all folds (CPCV or WalkForward)
     ↓
Collect Sharpe per fold → not one number, but N numbers
     ↓
PBO(returns_matrix) → probability that best strategy is overfit
DSR(sharpe, n_trials) → p-value corrected for multiple testing
BootstrapSharpeCI(returns) → 95% confidence interval
     ↓
IF PBO < 0.5 AND DSR p < 0.05 AND CI doesn't include 0
THEN promote strategy
ELSE reject
```

**Cosa rende unico CPCV vs walk-forward esistente**:
- Combinatorial Purged Cross-Validation (López de Prado 2018)
- C(N,K) combinazioni vs semplice rolling window
- purge + embargo eliminates temporal leakage
- Φ paths ricostruite da combinazioni → K test set diversi per ogni barra

**Perché non è overlap**: Oracle ha walk_forward.py ma non CPCV, non PBO, non DSR, non Bootstrap Sharpe CI.

**Licenza**: AGPL-3.0 → prendere SOLO ispirazione, non copiare codice. Reimplementare i tre splitter (struttura dataclass + logica split) e i tre indicatori.

### Risultato netto
- **Cross-validation robusta** (CPCV + PurgedKFold)
- **Multipla correzione test** (DSR per N trials)
- **Probabilità di overfitting** (PBO)
- **Intervallo di confidenza** (bootstrap Sharpe)

---

## 3. PyPortfolioOpt (4.5K⭐, MIT) — Portfolio Construction

### Cosa NON portare
| Modulo PyPortfolioOpt | Perché NO |
|-----------------------|-----------|
| `EfficientFrontier` base | Oracle non fa mean-variance classica |
| `expected_returns` | Oracle ha previsioni dai segnali |
| `discrete_allocation` | Oracle ha risk-kernel sizing |

### Cosa PORTARE

| Cosa | API PyPortfolioOpt | File Oracle Target | Stima |
|------|-------------------|-------------------|-------|
| **HRP (Hierarchical Risk Parity)** | `HRPOpt(returns).optimize()` | `analytics/portfolio/hrp.py` | 2gg |
| **Covariance shrinkage** | `risk_models.CovarianceShrinkage` | `analytics/portfolio/covariance.py` | 1gg |
| **Black-Litterman views** | `BlackLittermanModel(Sigma, views)` | `analytics/portfolio/black_litterman.py` | 3gg |

### Pattern d'integrazione — HRP nell'Ensemble

```
Come funziona ORA:
  RegimeAwareEnsemble.routing:
    choppy → mean_rev (solid weight 1.0)
    bull   → trend    (solid weight 1.0)

Come funziona DOPO:
  Ogni strategia → FactorTimingEngine → IC score
  IC score → PyPortfolioOpt.HRPOpt(returns) → weights dinamici
  Ensemble.compute() usa weights invece di routing binario
```

**Dettaglio HRP**:
```python
# analytics/portfolio/hrp.py
from pypfopt import HRPOpt


def compute_strategy_weights(
    returns_df: pd.DataFrame,  # columns = strategy names
) -> dict[str, float]:
    """Compute Hierarchical Risk Parity weights for strategy allocation."""
    hrp = HRPOpt(returns_df)
    weights = hrp.optimize()
    # weights: {"EmaTrend_10_30": 0.15, "RsiReversion_14": 0.35, ...}
    return dict(weights)
```

**Perché non overlap**: Oracle attualmente usa routing BINARIO (1 vs 0). Con HRP diventa CONTINUO (0.2 + 0.3 + 0.5 = 1.0). Non sostituisce il routing — lo potenzia.

### Risultato netto
- **Pesi continui** invece di routing binario
- **HRP** riduce concentrazione su strategie simili
- **Black-Litterman** incorpora view degli analyst

---

## 4. pysystemtrade (2.5K⭐, BSD-3) — Forecast Scaling & Risk

### Cosa NON portare
| Modulo pysystemtrade | Perché NO |
|----------------------|-----------|
| `systems.backtest` | Oracle ha engine migliori |
| `systems.forecasting` | Oracle ha 52+ strategie |
| `systems.data` | Oracle ha BL-301 |
| `systems.portfolio` intero | Oracle ha portfolio construction via PyPortfolioOpt |

### Cosa PORTARE

| Cosa | Funzione pysystemtrade | File Oracle Target | Stima |
|------|----------------------|-------------------|-------|
| **Vol target** | `get_vol_target_dict()` → annual_cash_vol_target | `core/risk/vol_target.py` | 2gg |
| **Forecast scaling** | `avg_abs_forecast()` → forecast_scalar | `analytics/portfolio/forecast_scaling.py` | 2gg |
| **IDM** | Instrument Diversification Multiplier | `core/risk/idm.py` | 1gg |
| **Forecast combination** | `get_combined_forecast()` weighted by Sharpe | `analytics/portfolio/forecast_combine.py` | 2gg |

### Pattern d'integrazione

```
Signal raw (-1/0/1) — Oracle segnali binari attuali
     │
     ▼
Forecast scaling (pysystemtrade):
  Dal raw binario a forecast continuo [-10, +10]
  forecast = raw * forecast_scalar
  dove forecast_scalar = 10 / avg_abs(raw_signal)
  rende comparabili strategie con scale diverse
     │
     ▼
Forecast combination (pysystemtrade):
  combined_forecast = sum(weight_i * forecast_i)
  dove weight_i = Sharpe_i / sum(Sharpe_j)
     │
     ▼
IDM = 1 / sqrt(avg_correlation_between_forecasts)
  Più strategie sono correlate, meno IDM scala
  reward vera diversificazione
     │
     ▼
Position sizing (pysystemtrade + Oracle):
  pos = vol_target * combined_forecast * IDM / current_vol
  dove vol_target = 25% annuale (Carver default)
```

**Carver's forecast scaling spiegato**:
```
pysystemtrade: raw signal [-1, 0, +1] → forecast [-10, 0, +10]
Media historical forecast ≈ 0
Avg absolute forecast ≈ 10 (dopo scaling)

Questo permette combinare forecasts:
- EMA crossover forecast = +8 (strong trend)
- RSI reversion forecast = -5 (moderate mean-rev bet)
- Combined = 0.3*8 + 0.7*(-5) = +0.6 (slightly bullish, scaled by IDM)
```

**Cosa NON sostituisce**: OracleRiskManager esiste e gestisce daily loss, overall loss, contract caps. pysystemtrade pos sizing si AGGIUNGE per lo scaling continuo.

### Risultato netto
- **Posizioni continue** invece di -1/0/1
- **Diversificazione premiata** via IDM
- **Vol targeting** sistematico (Carver standard)
- **Forecast comparabili** tra strategie diverse

---

## 5. Mappa Integrazione Finale — Architettura

```
                         ┌──────────────────────┐
                         │   BL-301 Data Lake     │
                         │   (7 sources, 22K+    │
                         │    parquet files)      │
                         └───────┬───────────────┘
                                 │
                   ┌─────────────▼──────────────┐
                   │  Oracle Strategy Signals     │
                   │  (signals.py r1 r2 + QLib   │
                   │   Alpha101 adapters  ← QLib │
                   └─────────────┬──────────────┘
                                 │
                   ┌─────────────▼──────────────┐
                   │  Factor Timing Engine       │
                   │  (Rank IC, ICIR, decay)     │
                   │  [già implementato]         │
                   └─────────────┬──────────────┘
                                 │ IC scores
                   ┌─────────────▼──────────────┐
                   │  PyPortfolioOpt.HRP          │
                   │  → weights per strategy      │
                   │  [da implementare]           │
                   └─────────────┬──────────────┘
                                 │ weights
                   ┌─────────────▼──────────────┐
                   │  pysystemtrade              │
                   │  Forecast combination + IDM │
                   │  Forecast scaling           │
                   │  [da implementare]          │
                   └─────────────┬──────────────┘
                                 │ scaled forecast
                   ┌─────────────▼──────────────┐
                   │  RegimeAwareEnsemble        │
                   │  + RoutingDecision          │
                   │  [esistente]                │
                   └─────────────┬──────────────┘
                                 │
                   ┌─────────────▼──────────────┐
                   │  Paper Execution + Risk     │
                   │  (OrderManager, RiskKernel, │
                   │   Ledger, Reconciliation)   │
                   └─────────────┬──────────────┘
                                 │
                   ┌─────────────▼──────────────┐
                   │  Inalpha overfitting checks │
                   │  CPCV · PBO · DSR · SharpeCI│
                   │  [da implementare]          │
                   └─────────────┬──────────────┘
                                 │ validates
                   ┌─────────────▼──────────────┐
                   │  Strategy Evolution         │
                   │  (3 gates + backtest)       │
                   │  [già implementato]         │
                   └───────────────────────────┘
```

---

## 6. Priorità d'Implementazione

| # | Framework | Cosa | Perché prima | Stima |
|---|-----------|------|-------------|-------|
| 1 | **PyPortfolioOpt** | HRP weights | Sblocca portfolio continuo subito | 2gg |
| 2 | **pysystemtrade** | Forecast scaling + IDM | Sblocca sizing continuo subito | 3gg |
| 3 | **Inalpha** | CPCV + PBO + DSR | Serve per validare strategie | 4gg |
| 4 | **QLib** | Alpha101 adapter | Più strategie da testare | 4gg |

**Stima totale**: 13gg di implementazione

---

## 7. Nessun Overlap — Verifica Finale

| Cosa fa Oracle oggi | Framework | Enhancement | Tipo |
|--------------------|-----------|-------------|------|
| Routing binario (1/0) | PyPortfolioOpt | Pesi continui (HRP) | Enhancement |
| Sizing lot intero (-1/0/1) | pysystemtrade | Forecast scaling continuo | Enhancement |
| Walk-forward esiste (parziale) | Inalpha | CPCV + PBO + DSR da zero | Nuovo |
| Signal library (52 strategie) | QLib | +100 alpha definitions | Nuovo |
| FactorTimingEngine (IC ranking) | — | Già implementato | Done |
| ResearchMemory | — | Già implementato | Done |
| Strategy Evolution gates | — | Già implementato | Done |
