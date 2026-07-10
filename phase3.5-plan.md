# Phase 3.5 — Signal Optimization

> 2 settimane · 4 task · Affinamento segnali GA per convergenza reale
> Obiettivo: Sharpe > 0.8 in backtest WalkForward su SPY 2015-2020

---

## 1. Problema

Il `KNNGenomeToSignal` produce **1460 segnali su 1510** (96% attivi) ma Sharpe ancora piatta:

- **KNN polarizzato BUY**: su SPY 2015-2020 (+103%), l'80% dei neighbors storici predice UP
- **Voto maggioritario sbilanciato**: classe BUY domina, classe SELL sottorappresentata
- **Nessuna ottimizzazione direzionale**: il GA non trova edge perché il segnale è sempre "quasi-long"
- **OHLCV rumoroso**: dati grezzi introducono noise che il KNN fatica a filtrare

## 2. Soluzioni

### Task 1: Heikin Ashi Conversion

Convertire OHLCV in Heikin Ashi per ridurre noise e migliorare la qualità del segnale:

```
HA_Close = (open + high + low + close) / 4
HA_Open = (previous_HA_Open + previous_HA_Close) / 2
HA_High = max(high, HA_Open, HA_Close)
HA_Low = min(low, HA_Open, HA_Close)
```

**Files:** `genetics/signal/heikin_ashi.py`, test

### Task 2: KNN Class Balancing

Bilanciare il voto KNN per evitare polarizzazione:

| Tecnica | Effetto |
|---------|---------|
| **Class weights** | Penalizza la classe maggioritaria (BUY) nel voto |
| **Adaptive threshold** | Soglia dinamica basata su distribuzione storica labels |
| **Stratified sampling** | Seleziona K neighbors con distribuzione bilanciata |
| **Distance-weighted vote** | Neighbors più vicini pesano di più nel voto |

**Files:** `genetics/genome/knn_signal.py` (modifiche mirate)

### Task 3: Segnale Ibrido (KNN + Alpha Factors)

Combinare KNN con i 50 alpha factors per segnali più robusti:

```
Segnale = α × KNN_signal + (1-α) × Alpha_signal
```

**Files:** `genetics/genome/hybrid_signal.py`

### Task 4: GA Run Ottimizzata

- pop=20, gen=20, 4 isole, 5-fold WFA
- Parametri: 9 KNN + 1 hybrid_weight = 10 parametri
- Goal: Sharpe > 0.8 in backtest

---

## 3. Esecuzione

```
Week 1: T1 (Heikin Ashi) + T2 (KNN balancing) — parallelo
Week 2: T3 (Hybrid signal) + T4 (GA run + showcase) — in serie
```
