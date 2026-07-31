# Integrazione Kairos-v2 + FinClaw/StratEvo in Oracle

> Piano dettagliato — nessun overlap, solo potenziamento

---

## Fase 1: PyTorch Regime Classifier (da Kairos-v2)

### Stato attuale Oracle
- Regime detector: 6-detector EnsembleVoter + SMA20/50 heuristic
- 4 regimi: BULL, BEAR, CHOPPY, VOLATILE
- 56% del tempo classifica "choppy" — troppo conservativo

### Cosa prende da Kairos-v2

```python
# ml/trang_thai_thi_truong_ml/ml_model.py
class TradingMLP(nn.Module):
    """Input 80-dim (18 features × 4 TF + 8 ctx)
    → 3 × ResBlock(256, Dropout=0.3)
    → Output 8 classi regime"""
```

**Architettura esatta:**
- Input: 80 features normalizzate (z-score)
- Input layer: Linear(80→256) + BatchNorm + GELU + Dropout(0.15)
- 3× ResBlock(256, Dropout=0.3) — ognuno: Linear(256→256) + BN + GELU + Dropout + Linear(256→256) + residual
- Output layer: Linear(256→64) + BN + GELU + Dropout(0.3) → Linear(64→8)

### Cosa integrare in Oracle

```
analytics/regime/ml_classifier.py  (NUOVO)
└── class TradingMLP(nn.Module)     — PyTorch model identico a Kairos-v2
└── class AI_Engine                  — Singleton load/predict
└── train_regime_classifier()       — Allenamento su dati storici
└── compute_18_core_features()       — Feature engineering identico
```

### Le 18 feature core (da `tao_feature.py`)

| # | Feature | Descrizione | Calcolo |
|---|---------|------------|---------|
| 1 | **D** | EMA distance | `(close - ema_50) / close` |
| 2 | **S** | EMA slope | `ema_50.slope(3)` |
| 3 | **ADX** | Trend strength | ADX(14) |
| 4 | **RSI** | Momentum | RSI(14) |
| 5 | **RSIslope** | RSI change | RSI - RSI.shift(3) |
| 6 | **ROC** | Rate of change | `close / close.shift(10) - 1` |
| 7 | **ATRn** | Normalized ATR | ATR(14) / close |
| 8 | **VOLz** | Volume z-score | `(vol - vol_ma20) / vol_std20` |
| 9 | **SpreadATR** | Spread vs ATR | `(high - low) / ATR` |
| 10 | **BBwidth** | Bollinger width | `(bb_upper - bb_lower) / sma20` |
| 11 | **SQZ** | Bollinger/Keltner squeeze | `(bb_width - kc_width) / bb_width` |
| 12 | **CHOP** | Choppiness index | Chop(14) |
| 13 | **ER** | Efficiency ratio | Kavak ER(10) |
| 14 | **BBpctB** | Bollinger %B | `(close - bb_lower) / (bb_upper - bb_lower)` |
| 15 | **VWAPd** | VWAP distance | `(close - vwap) / close` |
| 16 | **WickUpProp** | Upper wick proportion | `(high - max(open,close)) / (high - low)` |
| 17 | **WickDnProp** | Lower wick proportion | `(min(open,close) - low) / (high - low)` |
| 18 | **BodyProp** | Body proportion | `abs(close - open) / (high - low)` |

**Calcolate su 4 timeframe: 5m, 15m, 1h, 4h** → 72 feature
+ 8 feature di contesto (ora del giorno, day of week, vol ratio) = **80-dim input**

### Output: 8 regimi

| # | Regime | Traduzione | Azione suggerita |
|---|--------|-----------|-----------------|
| 0 | Dong_Bang | Congelato | Niente trade |
| 1 | Nen_Chat | Compressione | Prepararsi a breakout |
| 2 | Dau_XH | Inizio uptrend | Trend long |
| 3 | XH_Manh | Uptrend forte | Trend long aggressivo |
| 4 | Cao_Trao | Climax | Take profit / inversione |
| 5 | Hoi_Quy | Regressione/ritraccio | Mean reversion |
| 6 | Nhieu_Dong | Noisy/choppy | Evitare / scalping |
| 7 | Quet_TK | Stop hunting | Aspettare conferma |

### Allenamento

```python
def train_regime_classifier(df_ohlcv: pl.DataFrame) -> None:
    # 1. Calcola 18 core features su 4 TF
    # 2. Label: price_change_next_5_bars > threshold → regime
    # 3. Train/Test split con walk-forward
    # 4. Loss: CrossEntropyLoss con WeightedRandomSampler
    # 5. Optimizer: Adam(lr=1e-4)
    # 6. Epochs: 200 con early stopping
    # 7. Salva: model_pytorch.pth + scaler_params.json
```

---

## Fase 2: 484+ Genetic Algorithm Factors (da FinClaw/StratEvo)

### Stato attuale Oracle
- 52 strategie in signals.py / signals_r1.py / signals_r2.py
- 17 Alpha101 in catalog/alpha101.py
- **Totale: 69 strategie**

### Cosa prende da FinClaw

FinClaw/StratEvo ha 484 fattori organizzati in:

```
faktori/
├── momentum/        (64 fattori)
├── trend/           (58 fattori)
├── volatility/      (42 fattori)
├── volume/          (36 fattori)
├── correlation/     (28 fattori)
├── seasonal/        (24 fattori)
├── microstructure/  (32 fattori)
├── cross_asset/     (22 fattori)
└── alternative/     (178 fattori)  — include:
    ├── fundamental/ (56 fattori)
    ├── macro/        (48 fattori)
    └── sentiment/   (74 fattori)
```

### Integrazione in Oracle

```
analytics/strategy/catalog/finclaw_factors.py  (NUOVO — 484 fattori)
└── FINCLAW_484: dict[str, Callable]  — mappa nome→funzione come Alpha101

Formato ogni fattore:
    def factor_NNN(data: pl.DataFrame) -> pl.Series:
        """Descrizione. Segnale: -1/0/1."""
        ...
        return pl.Series("signal", signal)
```

### GA Evolution Loop

Invece di importare tutto FinClaw, implementiamo il GA loop direttamente
in Oracle usando la nostra infrastruttura esistente:

```
genetics/
├── evolution.py           (già esistente — sandbox gates)
├── population.py          (NUOVO — GA population management)
├── crossover.py           (NUOVO — DNA crossover operators)
├── mutation.py            (NUOVO — DNA mutation operators)
└── fitness.py             (NUOVO — multi-objective fitness)
```

**DNA di una strategia** = vettore di pesi per i 484 fattori + parametri risk

```python
@dataclass
class DNA:
    factor_weights: np.ndarray  # [484] float32, softmax
    risk_params: dict  # stop_loss_pct, take_profit_pct, sizing
```

**Algoritmo GA:**

```
1. Inizializza popolazione: 100 DNA casuali
2. Per ogni generazione (max 50):
   a. Walk-forward test per ogni DNA su 3 anni di dati
   b. Fitness = Sharpe × Calmar / Turnover
   c. Seleziona top 20% (tournament selection)
   d. Crossover: uniform crossover tra coppie di top
   e. Mutazione: 10% dei pesi modificati ± Gaussian noise
   f. Rimpiazzo: elitarismo (keep top 3) + nuovi figli
3. Il DNA con fitness maggiore → strategy.py deployabile
```

---

## Fase 3: Fine-tuning del modello (retraining online)

Kairos-v2 implementa un ciclo di apprendimento continuo:

```python
# Dal bot in esecuzione: registra risultato trade → regime corrente
tu_dong_hoc_tu_log():
    # Ogni 1000 trade:
    # 1. Carica log esecuzione
    # 2. Crea dataset (feature → regime_corretto)
    # 3. Retrain con WeightedRandomSampler
    # 4. Salva nuovo model_pytorch.pth
```

In Oracle questo diventa:

```python
# Dopo ogni 100 sessioni paper:
regime_classifier.retrain(trade_log_db)
```

---

## Piano di Implementazione

| Fase | Cosa | Dove | Dipende da | Giorni |
|------|------|------|-----------|:------:|
| 1a | TradingMLP model class | `analytics/regime/ml_classifier.py` | — | 1 |
| 1b | 18 core features | `analytics/regime/ml_features.py` | — | 1 |
| 1c | Training pipeline | `scripts/train_regime_classifier.py` | 1a+1b | 1 |
| 1d | Integrazione in ensemble | `analytics/strategy/adaptive_ensemble.py` | 1c | 1 |
| 2a | FinClaw 484 factors | `analytics/strategy/catalog/finclaw_factors.py` | — | 4 |
| 2b | GA population/crossover/mutation | `genetics/population.py` | — | 2 |
| 2c | GA evolution loop completo | `scripts/run_ga_evolution.py` | 2a+2b | 2 |
| 3 | Online retraining loop | `analytics/regime/ml_classifier.py` | 1d+2c | 1 |

**Totale: ~13 giorni di implementazione**

---

## Deliverable Finale

Dopo l'integrazione, Oracle avrà:

- **8 regimi di mercato** invece di 4 (PyTorch ResBlock, non SMA heuristic)
- **553 strategie** invece di 69 (484 FinClaw + 17 Alpha101 + 52 esistenti)
- **GA evolution loop** che trova automaticamente le combinazioni migliori
- **Online retraining** che adatta il modello ai cambiamenti di mercato

Il sistema diventa una **fabbrica di edge automatica**: lancia GA evolution, aspetta 50 generazioni, deploya il DNA migliore. Nessun tuning manuale.
